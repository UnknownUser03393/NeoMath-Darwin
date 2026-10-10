#include <pybind11/pybind11.h>

#include "api.hpp"

namespace py = pybind11;
using namespace neomath::bindings;

PYBIND11_MODULE(neomath_core, module) {
    module.doc() = "NeoMath coarse-grained C++20 mathematics core";
    module.attr("__version__") = "1.0.0";
    module.def("parse_document", &parseDocumentApi, py::arg("source"));
    module.def("analyze_document", &analyzeDocumentApi, py::arg("document"));
    module.def("run_trace", &runTraceApi, py::arg("document"));
    module.def("replay", &replayApi, py::arg("document"), py::arg("changed_step"));
    module.def("get_completions", &getCompletionsApi, py::arg("document"), py::arg("step"));
    module.def("execute_transformation", &executeTransformationApi, py::arg("document"),
               py::arg("step"), py::arg("intent"));
    module.def("evaluate_probe", &evaluateProbeApi, py::arg("document"), py::arg("probe"));
    module.def("get_capabilities", &getCapabilitiesApi);
}
