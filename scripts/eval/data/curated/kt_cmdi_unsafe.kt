fun handler(host: String) {
    // command injection: concatenated user input passed to Runtime.exec
    Runtime.getRuntime().exec("ping " + host)
}
