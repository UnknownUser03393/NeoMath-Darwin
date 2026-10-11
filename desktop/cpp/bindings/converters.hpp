#pragma once

#include <pybind11/pybind11.h>

#include "neomath/semantics/engine.hpp"

namespace neomath::bindings {

namespace py = pybind11;

py::dict documentToPython(const Document& document);
py::dict stateToPython(const MathState& state);
py::dict traceToPython(const ExecutionTrace& trace);
py::list probeTraceToPython(const std::vector<ProbeStepEvaluation>& evaluations);
py::list completionsToPython(const std::vector<Completion>& completions);
py::dict transformationToPython(const TransformationResult& transformation);
py::dict capabilitiesToPython(const std::map<std::string, std::string>& values);

}  // namespace neomath::bindings
