package com.example.sdkdemo.base

import android.app.AlertDialog
import android.content.DialogInterface
import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import androidx.annotation.StringRes
import androidx.appcompat.app.AppCompatActivity
import com.example.sdkdemo.R
import com.example.sdkdemo.WebViewActivity

abstract class BaseSampleActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = getString(titleRes())
    }

    @StringRes
    abstract fun titleRes(): Int

    override fun onCreateOptionsMenu(menu: Menu?): Boolean {
        menuInflater.inflate(R.menu.menu_main, menu)
        return super.onCreateOptionsMenu(menu)
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            R.id.menu_official_website -> {
                openOfficialWebsite()
                return true
            }
        }
        return super.onOptionsItemSelected(item)
    }

    private fun openOfficialWebsite() {
//        val uri = Uri.parse(getString(R.string.official_website_url))
        val intent = Intent(this, WebViewActivity::class.java)
        intent.putExtra("uri", getString(R.string.official_website_url))
        startActivity(intent)
//        WebViewActivity.start(getString(R.string.official_website_url), this)
    }

    protected fun showTipDialog(message: String) {
        AlertDialog.Builder(this)
            .setCancelable(true)
            .setTitle("提示")
            .setMessage(message)
            .setPositiveButton("OK"
            ) { dialog, which -> dialog?.dismiss() }
            .show()
    }
}