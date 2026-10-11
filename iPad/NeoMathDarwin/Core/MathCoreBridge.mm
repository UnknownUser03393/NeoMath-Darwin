#import "MathCoreBridge.h"
#include "neomath/semantics/engine.hpp"
#include <regex>
#include <mutex>
static std::mutex cacheMutex;
static std::optional<neomath::ExecutionTrace> cachedTrace;
static std::vector<std::string> cachedSources;
using namespace neomath;
static NSString *str(const std::string &s) { return [NSString stringWithUTF8String:s.c_str()] ?: @""; }
static NSArray *values(const auto &vs) { NSMutableArray *a = [NSMutableArray array]; for (const auto &v : vs) [a addObject:str(v.toString())]; return a; }
static NSString *setText(const SolutionSet &s) {
    switch(s.kind) {
        case SolutionKind::Finite: return [NSString stringWithFormat:@"{%@}", [values(s.values) componentsJoinedByString:@", "]];
        case SolutionKind::Empty: return @"∅";
        case SolutionKind::AllReal: return @"ℝ";
        case SolutionKind::AllRealExcludingFinite: return [NSString stringWithFormat:@"ℝ ∖ {%@}", [values(s.excluded) componentsJoinedByString:@", "]];
        default: return @"Unverified";
    }
}
static NSString *domainText(const DomainSet &s) {
    switch(s.kind) {
        case DomainKind::AllReal: return @"ℝ";
        case DomainKind::Empty: return @"∅";
        case DomainKind::RealExcludingFinite: return [NSString stringWithFormat:@"ℝ ∖ {%@}", [values(s.excluded) componentsJoinedByString:@", "]];
        case DomainKind::Interval: return [NSString stringWithFormat:@"%@%@, %@%@", s.lowerInclusive ? @"[" : @"(", s.lower ? str(s.lower->toString()) : @"−∞", s.upper ? str(s.upper->toString()) : @"∞", s.upperInclusive ? @"]" : @")"];
        default: return @"Unverified";
    }
}
static NSData *json(id object) { return [NSJSONSerialization dataWithJSONObject:object options:0 error:nil]; }
static NSData *failure(const std::exception &e) { return json(@{@"error": str(e.what())}); }
@implementation MathCoreBridge
+ (NSData *)trace:(NSString *)source {
    try {
        std::lock_guard lock(cacheMutex);
        auto document = parseDocument(source.UTF8String);
        size_t reusable = 0;
        while (reusable < document.steps.size() && reusable < cachedSources.size() && document.steps[reusable].source == cachedSources[reusable]) ++reusable;
        auto trace = cachedTrace && reusable > 0 ? replayTrace(document, *cachedTrace, reusable) : runTrace(document);
        cachedTrace = trace; cachedSources.clear();
        for (const auto &step : document.steps) cachedSources.push_back(step.source);
        NSMutableArray *steps = [NSMutableArray array];
        for (size_t i = 0; i < trace.states.size(); ++i) {
            const auto &s = trace.states[i]; const auto &d = trace.diagnostics[i];
            NSArray *names = @[@"valid", @"root_fault", @"tainted", @"independent_fault", @"unverified", @"unsupported"];
            NSMutableDictionary *row = [@{@"source":str(s.source), @"solutions":setText(s.solutionSet), @"domain":domainText(s.domain), @"status":names[(int)d.status], @"title":str(d.title), @"message":str(d.message), @"reason":str(s.reason)} mutableCopy];
            if (i < document.steps.size() && document.steps[i].error) {
                row[@"status"] = @"parse_error"; row[@"title"] = @"Syntax error";
                row[@"message"] = str(document.steps[i].error->message);
            }
            if (i > 0 && i - 1 < trace.relations.size()) {
                const auto &r = trace.relations[i-1];
                row[@"lost"] = values(r.lostSolutions); row[@"gained"] = values(r.gainedSolutions);
                row[@"relation"] = str(r.reason);
                if (r.probe) {
                    const auto &p = *r.probe;
                    row[@"witness"] = str(p.value.toString());
                    if (p.previousLeftValue) row[@"previousLeft"] = str(p.previousLeftValue->toString());
                    if (p.previousRightValue) row[@"previousRight"] = str(p.previousRightValue->toString());
                    if (p.currentLeftValue) row[@"left"] = str(p.currentLeftValue->toString());
                    if (p.currentRightValue) row[@"right"] = str(p.currentRightValue->toString());
                    row[@"before"] = !p.previousDefined ? @"Undefined" : p.previousPredicateResult.has_value() ? (*p.previousPredicateResult ? @"True" : @"False") : @"Unknown";
                    row[@"after"] = !p.currentDefined ? @"Undefined" : p.currentPredicateResult.has_value() ? (*p.currentPredicateResult ? @"True" : @"False") : @"Unknown";
                }
            }
            [steps addObject:row];
        }
        return json(@{@"steps":steps, @"durationMs":@(trace.durationMs), @"cacheHits":@(reusable), @"method":reusable > 0 ? @"replay" : @"full", @"engine":@"C++20"});
    } catch (const std::exception &e) { return failure(e); }
}
+ (NSData *)completions:(NSString *)source step:(NSInteger)step {
    try {
        auto items = getCompletions(parseDocument(source.UTF8String), (size_t)step);
        NSMutableArray *rows = [NSMutableArray array];
        for (const auto &item : items) [rows addObject:@{@"id":str(item.id), @"label":str(item.label), @"risk":str(item.risk), @"available":@(item.available), @"reason":str(item.reason), @"preview":str(item.preview)}];
        return json(@{@"items":rows});
    } catch (const std::exception &e) { return failure(e); }
}
+ (NSData *)probe:(NSString *)source value:(NSString *)value {
    try {
        std::string text(value.UTF8String); std::smatch match;
        if (!std::regex_match(text, match, std::regex(R"((-?[0-9]+)(/([0-9]+))?)")))
            throw std::runtime_error("Enter an exact rational, e.g. 0 or 1/2");
        Rational v(std::stoll(match[1].str()), match[3].matched ? std::stoll(match[3].str()) : 1);
        auto evaluations = evaluateProbe(parseDocument(source.UTF8String), v);
        NSMutableArray *steps = [NSMutableArray array];
        for (const auto &e : evaluations) {
            NSMutableDictionary *row = [@{@"source": @"", @"solutions": @"", @"domain": @"", @"status": @"probe", @"title": @"Substitution", @"message": e.defined ? @"Defined" : @"Undefined", @"reason": e.reason ? str(*e.reason) : @"", @"witness": str(v.toString()), @"after": !e.defined ? @"Undefined" : e.predicateResult.has_value() ? (*e.predicateResult ? @"True" : @"False") : @"Unknown"} mutableCopy];
            if (e.leftValue) row[@"left"] = str(e.leftValue->toString());
            if (e.rightValue) row[@"right"] = str(e.rightValue->toString());
            [steps addObject:row];
        }
        return json(@{@"steps":steps});
    } catch (const std::exception &e) { return failure(e); }
}
+ (NSData *)transform:(NSString *)source step:(NSInteger)step intent:(NSString *)intent {
    try {
        auto r = executeTransformation(parseDocument(source.UTF8String), (size_t)step, intent.UTF8String);
        return json(@{@"applied":@(r.applied), @"source":str(r.source), @"reason":str(r.reason)});
    } catch (const std::exception &e) { return failure(e); }
}
+ (NSData *)transform:(NSString *)source step:(NSInteger)step intent:(NSString *)intent argument:(NSString *)argument {
    try {
        auto r = executeTransformation(parseDocument(source.UTF8String), (size_t)step, intent.UTF8String, std::string(argument.UTF8String));
        return json(@{@"applied":@(r.applied), @"source":str(r.source), @"reason":str(r.reason)});
    } catch (const std::exception &e) { return failure(e); }
}
@end
