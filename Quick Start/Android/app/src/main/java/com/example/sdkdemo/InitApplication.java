package com.example.sdkdemo;

import android.app.Application;
import android.util.Log;
import android.widget.Toast;

import androidx.annotation.NonNull;

import com.blankj.utilcode.util.ProcessUtils;
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

        /**
         * 目前仅支持在主进程中初始化VePhoneEngine
         */
        if (ProcessUtils.isMainProcess()) {
            /**
             * 请使用prepare()方法来初始化VeGameEngine，init()方法已废弃。
             */
            VePhoneEngine.getInstance().prepare(this);

            // 设置为true时会打印SDK内部日志，由于日志比较多，建议release版本设置为false
            VePhoneEngine.setDebug(true);
            VePhoneEngine.getInstance().addCloudCoreManagerListener(new ICloudCoreManagerStatusListener() {
                /**
                 * 请在onPrepared()回调中监听VeGameEngine的生命周期，onInitialed()回调已废弃
                 */
                @Override
                public void onInitialed() {

                }

                @Override
                public void onPrepared() {
                    // SDK初始化是一个异步过程，在这个回调中监听初始化完成状态
                    AcLog.d(TAG, "onPrepared :" + VePhoneEngine.getInstance().getStatus());
                }
            });
        }
        else {
            Toast.makeText(this, "请在主进程进行初始化!", Toast.LENGTH_LONG).show();
        }
    }
}
