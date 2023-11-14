package com.example.sdkdemo

import android.Manifest
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import com.blankj.utilcode.util.PermissionUtils
import com.example.sdkdemo.base.BaseSampleActivity
import com.example.sdkdemo.util.AssetsUtil
import com.example.sdkdemo.util.Feature

class FeatureActivity : BaseSampleActivity() {

    private var mFeatureId = -1

    private lateinit var etPodId: EditText
    private lateinit var etProductId: EditText
    private lateinit var etClarityId: EditText
    private lateinit var etRoundId: EditText
    private lateinit var btnStartPhone: Button

    // 这里请输入你的podId和productId
    private val testBean = TestBean(podId = "7292728071466179382", productId = "1591495366954455040")

    override fun onCreate(savedInstanceState: Bundle?) {
        mFeatureId = intent.getIntExtra("featureId", -1)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_startphone)
        initView()
    }

    private fun initView() {
        etPodId = findViewById(R.id.et_podId)
        etProductId = findViewById(R.id.et_productId)
        etRoundId = findViewById(R.id.et_roundId)
        etClarityId = findViewById(R.id.et_clarityId)
        etPodId.setText(testBean.podId)
        etProductId.setText(testBean.productId)
        etRoundId.setText(testBean.roundId)
        etClarityId.setText(testBean.clarityId)

        btnStartPhone = findViewById(R.id.btn_start_phone)
        btnStartPhone.setOnClickListener{
            if (!AssetsUtil.isAssetsFileExists(applicationContext, "sts.json")) {
                Toast.makeText(this, "Assets目录下sts.json文件不存在，请先创建文件！", Toast.LENGTH_SHORT).show()
            }
            else if (etPodId.text.isEmpty()) {
                Toast.makeText(this, "请输入podId", Toast.LENGTH_SHORT).show()
            }
            else if (etProductId.text.isEmpty()) {
                Toast.makeText(this, "请输入productId", Toast.LENGTH_SHORT).show()
            }
            else {
                PhoneActivity.startPhone(
                    etPodId.text.toString(),
                    etProductId.text.toString(),
                    etRoundId.text.toString(),
                    etClarityId.text.toString().toIntOrNull() ?: 1,
                    this,
                    mFeatureId
                )
            }
        }

        PermissionUtils.permission(
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.BLUETOOTH,
            Manifest.permission.WRITE_EXTERNAL_STORAGE,
            Manifest.permission.READ_EXTERNAL_STORAGE,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION
        ).request()
    }

    override fun titleRes(): Int {
        when (mFeatureId) {
            Feature.FEATURE_AUDIO -> {
                return R.string.audio
            }
            Feature.FEATURE_CAMERA -> {
                return R.string.camera
            }
            Feature.FEATURE_CLIPBOARD -> {
                return R.string.clipboard
            }
            Feature.FEATURE_FILE_EXCHANGE -> {
                return R.string.file_exchange
            }
            Feature.FEATURE_LOCAL_INPUT -> {
                return R.string.local_input
            }
            Feature.FEATURE_LOCATION -> {
                return R.string.location
            }
            Feature.FEATURE_MESSAGE_CHANNEL -> {
                return R.string.message_channel
            }
            Feature.FEATURE_PAD_CONSOLE -> {
                return R.string.pad_console
            }
            Feature.FEATURE_POD_CONTROL -> {
                return R.string.pod_control
            }
            Feature.FEATURE_SENSOR -> {
                return R.string.sensor
            }
            Feature.FEATURE_UNCLASSIFIED -> {
                return R.string.unclassified
            }
            else -> {
                return -1
            }
        }
    }
}