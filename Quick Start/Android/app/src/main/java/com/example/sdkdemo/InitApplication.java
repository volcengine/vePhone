package com.example.sdkdemo;

import android.app.Application;
import android.util.Log;

import androidx.annotation.NonNull;

import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.cloudphone.apiservice.outinterface.ICloudCoreManagerStatusListener;
import com.volcengine.cloudphone.apiservice.outinterface.InitListener;
import com.volcengine.phone.VePhoneEngine;

import org.jetbrains.annotations.NotNull;

public class InitApplication extends Application {

    private static final String TAG = "TAG_INIT";

    @Override
    public void onCreate() {
        super.onCreate();
        // 设置为true时会打印SDK内部日志，由于日志比较多，建议release版本设置为false
        VePhoneEngine.setDebug(true);
        VePhoneEngine.setLogger(new AcLog.ILogger() {
            @Override
            public void onVerbose(String s, String s1) {
                Log.v(s, s1);
            }

            @Override
            public void onDebug(String s, String s1) {
                Log.d(s, s1);
            }

            @Override
            public void onInfo(String s, String s1) {
                Log.i(s, s1);
            }

            @Override
            public void onWarn(String s, String s1) {
                Log.w(s, s1);
            }

            @Override
            public void onError(String s, String s1) {
                Log.e(s, s1);
            }

            @Override
            public void onError(String s, String s1, Throwable throwable) {
                Log.e(s, s1);
            }
        });
        VePhoneEngine.getInstance().addCloudCoreManagerListener(new ICloudCoreManagerStatusListener() {
            @Override
            public void onInitialed() {
                // sdk初始化是一个异步过程，在这个回调中监听初始化完成状态
                AcLog.d(TAG, "onInitialed :" + VePhoneEngine.getInstance().getStatus());
            }
        });
        // 调用SDK初始化接口
        VePhoneEngine.getInstance().init(this);
    }
}
