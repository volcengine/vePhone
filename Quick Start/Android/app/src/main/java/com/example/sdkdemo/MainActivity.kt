package com.example.sdkdemo

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.text.MessageFormat

class MainActivity : AppCompatActivity() {

    companion object {
        @JvmStatic
        val ak = "输入您的火山访问密钥ak"
        @JvmStatic
        val sk = "输入您的火山访问密钥sk"
        @JvmStatic
        val token = "输入您的火山访问token"
        @JvmStatic
        val productId = "输入您的火山云手机业务ID"
        @JvmStatic
        val uid by lazy { "phone_demo_" + System.currentTimeMillis() }
        @JvmStatic
        val podId = "输入您创建的podID"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<TextView>(R.id.tv_hint).apply {
            text = MessageFormat.format(
                "启动参数：\n" +
                        "[ak]: {0}\n" +
                        "[sk]: {1}\n" +
                        "[token]: {2}\n" +
                        "[productId]: {3}\n" +
                        "[uid]: {4}\n" +
                        "[podId]: {5}\n",
                ak, sk, token, productId, uid, podId
            )
        }
        findViewById<Button>(R.id.btn_start_phone).setOnClickListener {
            PhoneActivity.start(this@MainActivity)
        }
    }

}