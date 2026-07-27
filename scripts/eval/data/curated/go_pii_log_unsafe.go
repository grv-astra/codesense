package main

import "fmt"

func handler(user User) {
	fmt.Println(user.CustomerSsn) // privacy: logs a raw SSN
}
