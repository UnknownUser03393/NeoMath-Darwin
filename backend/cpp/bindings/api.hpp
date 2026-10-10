#pragma once

#include <pybind11/pybind11.h>

namespace neomath::bindings {

namespace py = pybind11;

py::dict parseDocumentApi(const std::string& source);
py::dict analyzeDocumentApi(const py::dict& document);
py::dict runTraceApi(const py::dict& document);
py::dict replayApi(const py::dict& document, std::size_t changedStep);
py::dict getCompletionsApi(const py::dict& document, std::size_t step);
py::dict executeTransformationApi(const py::dict& document, std::size_t step,
                                  const py::dict& intent);
py::dict evaluateProbeApi(const py::dict& document, const py::dict& probe);
py::dict getCapabilitiesApi();
py::dict errorResult(const std::string& type, const std::string& code, const std::string& message);

}  // namespace neomath::bindings
