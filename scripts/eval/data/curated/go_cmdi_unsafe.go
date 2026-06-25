package main

import (
	"os"
	"os/exec"
)

func handler(userInput string) {
	cmd := exec.Command(userInput, "list") // command injection: non-static command
	cmd.Stdout = os.Stdout
	cmd.Run()
}
