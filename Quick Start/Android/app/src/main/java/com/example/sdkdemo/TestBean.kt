package com.example.sdkdemo

data class TestBean(
    var podId: String,
    var productId: String,
    var roundId: String?= "123",
    var clarityId: String? = "1",
    var engineType: String = "BYTE_RTC",
)
