package com.example.sdkdemo

import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.widget.ProgressBar
import androidx.appcompat.app.AppCompatActivity

class WebViewActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_web_view)
        webView = findViewById(R.id.web_view)
        progressBar = findViewById(R.id.progress_bar)
        intent.getStringExtra("uri")?.let {
            webView.webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(view: WebView?, newProgress: Int) {
                    if (newProgress == 100) {
                        progressBar.visibility = View.GONE
                    }
                    else {
                        progressBar.visibility = View.VISIBLE
                        progressBar.progress = newProgress
                    }
                }
            }
            webView.loadUrl(it)
        }
    }
}