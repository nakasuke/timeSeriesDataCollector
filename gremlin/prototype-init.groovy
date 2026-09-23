// Return global bindings that Gremlin Server adds to the script engine.
// The remote clients alias their traversal source to the global name `g`.
def globals = [:]
globals << [g: graph.traversal()]
