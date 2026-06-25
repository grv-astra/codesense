<?php
function handler($mysqli) {
    $id = $_GET['id'];
    $stmt = $mysqli->prepare("SELECT * FROM users WHERE id = ?"); // safe: parameterized
    $stmt->bind_param("s", $id);
    $stmt->execute();
    return $stmt;
}
