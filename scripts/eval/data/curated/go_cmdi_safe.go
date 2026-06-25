package main

import (
	"os"
	"os/exec"
)

func handler(userInput string) {
	cmd := exec.Command("echo", userInput) // safe: static binary, arg passed separately
	cmd.Stdout = os.Stdout
	cmd.Run()
}
