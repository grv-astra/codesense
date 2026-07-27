package main

import "fmt"

func handler(user User) {
	fmt.Println(user.OrderID) // safe: not personal data
}
