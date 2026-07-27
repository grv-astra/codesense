<?php
function handler($user) {
    // privacy: logs a raw SSN
    error_log($user->customer_ssn);
}
