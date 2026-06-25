<?php
function handler() {
    $id = $_GET['id'];
    $query = "SELECT * FROM users WHERE id = '" . $id . "'"; // SQLi: tainted concat
    return mysql_query($query);
}
