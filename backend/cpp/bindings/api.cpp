#include "api.hpp"

#include <algorithm>
#include <chrono>
#include <deque>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

#include "converters.hpp"
#include "neomath/semantics/engine.hpp"
#include "neomath/algebra/polynomial.hpp"

using namespace pybind11::literals;

namespace neomath::bindings {
namespace {

template <typename Compute, typename Convert, typename CacheHits>
py::dict executeTimed(Compute&& compute, Convert&& convert, CacheHits&& cacheHits) {
    const auto started = std::chrono::steady_clock::now();
    try {
        using Result = decltype(compute());
        std::optional<Result> native;
        {
            py::gil_scoped_release release;
            native.emplace(compute());
        }
        py::dict response;
        response["ok"] = true;
        response["result"] = convert(*native);
        const auto duration =
            std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started)
                .count();
        response["metrics"] =
            py::dict("durationMs"_a = duration, "cacheHits"_a = cacheHits(*native));
        return response;
    } catch (const MathError& error) {
        return errorResult("math_error", error.code(), error.what());
    } catch (const std::exception& error) {
        return errorResult("internal_error", "CORE_OPERATION_FAILED", error.what());
    }
}

template <typename Compute, typename Convert>
py::dict executeTimed(Compute&& compute, Convert&& convert) {
    return executeTimed(std::forward<Compute>(compute), std::forward<Convert>(convert),
                        [](const auto&) { return 0; });
}

struct CachedTrace {
    std::vector<std::string> expressionSources;
    std::shared_ptr<const ExecutionTrace> trace;
};

struct ReplayComputation {
    ExecutionTrace trace;
    int cacheHits{};
};

constexpr std::size_t kTraceCacheCapacity = 8;
std::deque<CachedTrace> traceCache;
std::mutex traceCacheMutex;

std::vector<std::string> expressionSources(const Document& document) {
    std::vector<std::string> sources;
    sources.reserve(document.steps.size());
    for (const auto& step : document.steps) {
        if (step.kind == "expression") {
            sources.push_back(step.source);
        }
    }
    return sources;
}

void rememberTrace(std::vector<std::string> sources, const ExecutionTrace& trace) {
    std::lock_guard lock(traceCacheMutex);
    const auto existing = std::find_if(
        traceCache.begin(), traceCache.end(),
        [&sources](const CachedTrace& entry) { return entry.expressionSources == sources; });
    if (existing != traceCache.end()) {
        traceCache.erase(existing);
    }
    traceCache.push_front({std::move(sources), std::make_shared<ExecutionTrace>(trace)});
    if (traceCache.size() > kTraceCacheCapacity) {
        traceCache.pop_back();
    }
}

std::shared_ptr<const ExecutionTrace> bestCachedPrefix(const std::vector<std::string>& sources,
                                                       const std::size_t changedStep,
                                                       std::size_t& reusableStates) {
    std::lock_guard lock(traceCacheMutex);
    std::shared_ptr<const ExecutionTrace> best;
    reusableStates = 0;
    for (const auto& entry : traceCache) {
        const auto limit = std::min({changedStep, sources.size(), entry.expressionSources.size(),
                                     entry.trace->states.size()});
        std::size_t common = 0;
        while (common < limit && sources[common] == entry.expressionSources[common]) {
            ++common;
        }
        if (common > reusableStates) {
            reusableStates = common;
            best = entry.trace;
        }
    }
    return best;
}

ExecutionTrace analyzeAndRemember(const std::string& source) {
    const auto parsed = parseDocument(source);
    auto trace = runTrace(parsed);
    rememberTrace(expressionSources(parsed), trace);
    return trace;
}

ReplayComputation replayAndRemember(const std::string& source, const std::size_t changedStep) {
    const auto parsed = parseDocument(source);
    auto sources = expressionSources(parsed);
    std::size_t reusableStates = 0;
    const auto cached = bestCachedPrefix(sources, changedStep, reusableStates);
    auto trace = cached ? replayTrace(parsed, *cached, reusableStates) : runTrace(parsed);
    rememberTrace(std::move(sources), trace);
    return {std::move(trace), static_cast<int>(reusableStates)};
}

std::optional<std::string> extractSource(const py::dict& document) {
    if (document.contains("source") && py::isinstance<py::str>(document["source"])) {
        return py::cast<std::string>(document["source"]);
    }
    if (document.contains("result") && py::isinstance<py::dict>(document["result"])) {
        return extractSource(py::cast<py::dict>(document["result"]));
    }
    return std::nullopt;
}

py::dict invalidDocument() {
    return errorResult("validation_error", "DOCUMENT_SOURCE_REQUIRED",
                       "document.source must be a string");
}

std::optional<std::string> stringField(const py::dict& value, const char* key) {
    if (value.contains(key) && py::isinstance<py::str>(value[key])) {
        return py::cast<std::string>(value[key]);
    }
    return std::nullopt;
}

std::optional<std::string> transformationArgument(const py::dict& intent) {
    for (const auto* key : {"expression", "value", "by"}) {
        if (const auto value = stringField(intent, key); value.has_value()) {
            return value;
        }
    }
    if (intent.contains("arguments") && py::isinstance<py::dict>(intent["arguments"])) {
        const auto arguments = py::cast<py::dict>(intent["arguments"]);
        for (const auto* key : {"expression", "value", "by"}) {
            if (const auto value = stringField(arguments, key); value.has_value()) {
                return value;
            }
        }
    }
    return std::nullopt;
}

std::optional<Rational> parseProbeValue(const py::dict& probe) {
    if (!probe.contains("value")) {
        return std::nullopt;
    }
    try {
        if (py::isinstance<py::int_>(probe["value"])) {
            return Rational{py::cast<std::int64_t>(probe["value"])};
        }
        if (!py::isinstance<py::str>(probe["value"])) {
            return std::nullopt;
        }
        const auto text = py::cast<std::string>(probe["value"]);
        const auto parsed = parsePredicate("x=" + text);
        if (!parsed.predicate || parsed.predicate->alternatives.size() != 1) return std::nullopt;
        const auto converted = toRationalFunction(parsed.predicate->alternatives.front().right, 0);
        if (!converted.value || converted.value->numerator.degree() > 0 || converted.value->denominator.degree() > 0) return std::nullopt;
        return converted.value->numerator.coefficient(0) / converted.value->denominator.coefficient(0);
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

}  // namespace

py::dict parseDocumentApi(const std::string& source) {
    return executeTimed([&source] { return parseDocument(source); },
                        [](const Document& document) { return documentToPython(document); });
}

py::dict analyzeDocumentApi(const py::dict& document) {
    const auto source = extractSource(document);
    if (!source.has_value()) {
        return invalidDocument();
    }
    return executeTimed([source] { return analyzeAndRemember(*source); },
                        [](const ExecutionTrace& trace) { return traceToPython(trace); });
}

py::dict runTraceApi(const py::dict& document) { return analyzeDocumentApi(document); }

py::dict replayApi(const py::dict& document, const std::size_t changedStep) {
    const auto source = extractSource(document);
    if (!source.has_value()) {
        return invalidDocument();
    }
    return executeTimed(
        [source, changedStep] { return replayAndRemember(*source, changedStep); },
        [](const ReplayComputation& computation) { return traceToPython(computation.trace); },
        [](const ReplayComputation& computation) { return computation.cacheHits; });
}

py::dict getCompletionsApi(const py::dict& document, const std::size_t step) {
    const auto source = extractSource(document);
    if (!source.has_value()) {
        return invalidDocument();
    }
    return executeTimed(
        [source, step] {
            const auto parsed = parseDocument(*source);
            return getCompletions(parsed, step);
        },
        [](const std::vector<Completion>& values) { return completionsToPython(values); });
}

py::dict executeTransformationApi(const py::dict& document, const std::size_t step,
                                  const py::dict& intent) {
    const auto source = extractSource(document);
    if (!source.has_value()) {
        return invalidDocument();
    }
    if (!intent.contains("intent") || !py::isinstance<py::str>(intent["intent"])) {
        return errorResult("validation_error", "TRANSFORMATION_INTENT_REQUIRED",
                           "intent.intent must be a string");
    }
    const auto intentName = py::cast<std::string>(intent["intent"]);
    const auto argument = transformationArgument(intent);
    return executeTimed(
        [source, step, intentName, argument] {
            const auto parsed = parseDocument(*source);
            return executeTransformation(parsed, step, intentName, argument);
        },
        [](const TransformationResult& value) { return transformationToPython(value); });
}

py::dict evaluateProbeApi(const py::dict& document, const py::dict& probe) {
    const auto source = extractSource(document);
    if (!source.has_value()) {
        return invalidDocument();
    }
    const auto value = parseProbeValue(probe);
    if (!value.has_value()) {
        return errorResult("validation_error", "PROBE_VALUE_REQUIRED",
                           "probe.value must be an exact integer, decimal or rational string");
    }
    return executeTimed(
        [source, value] {
            const auto parsed = parseDocument(*source);
            return evaluateProbe(parsed, *value);
        },
        [value](const std::vector<ProbeStepEvaluation>& evaluations) {
            py::dict result;
            result["value"] = value->toString();
            result["steps"] = probeTraceToPython(evaluations);
            return result;
        });
}

py::dict getCapabilitiesApi() {
    return executeTimed([] { return capabilities(); },
                        [](const std::map<std::string, std::string>& values) {
                            return capabilitiesToPython(values);
                        });
}

}  // namespace neomath::bindings
