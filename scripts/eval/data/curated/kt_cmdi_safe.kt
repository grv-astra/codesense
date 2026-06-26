fun handler(host: String) {
    // safe: static binary, argument passed as a separate array element (no concat)
    Runtime.getRuntime().exec(arrayOf("ping", host))
}
