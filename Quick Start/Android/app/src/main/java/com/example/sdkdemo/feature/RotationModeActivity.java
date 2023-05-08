package com.example.sdkdemo.feature;

import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT;

import android.content.res.Configuration;
import android.os.Bundle;
import android.view.ViewGroup;
import android.view.WindowManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.example.sdkdemo.R;
import com.example.sdkdemo.ScreenUtil;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;


/**
 * 该类用于展示与rotation_mode相关的功能接口的使用方法
 */
public class RotationModeActivity extends AppCompatActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = getClass().getSimpleName();

    private ViewGroup mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_rotation_mode);
        initView();
        initPhonePlayConfig();
    }

    @Override
    protected void onResume() {
        super.onResume();
        VePhoneEngine.getInstance().resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VePhoneEngine.getInstance().pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        AcLog.d(TAG, "[onConfigurationChanged] newConfig: " + newConfig.orientation);

        /**
         * AUTO_ROTATION 模式下，需要 调用该方法;
         * PORTRAIT 模式下，不需要 调用该方法。
         */
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
    }

    private void initPhonePlayConfig() {
        /**
         * 这里需要替换成你的 ak/sk/token
         */
        String ak = "", sk = "", token = "";
        String sts = AssetsUtil.getTextFromAssets(this.getApplicationContext(), "sts.json");
        try {
            JSONObject stsJObj = new JSONObject(sts);
            ak = stsJObj.getString("ak");
            sk = stsJObj.getString("sk");
            token = stsJObj.getString("token");
        } catch (JSONException e) {
            e.printStackTrace();
        }

        /**
         * 这里需要替换成你的 podId和productId
         */
        String podId = "7225840879893175095";
        String productId = "1591495366954455040";
        String roundId = "roundId_123";
        String userId = "userId_" + System.currentTimeMillis();


        /**
         * rotation支持两种模式：AUTO_ROTATION 和 PORTRAIT，通过rotation()接口来设置。
         *
         * 1. AUTO_ROTATION 模式下，推流端(云端实例)会根据应用的横竖屏推送不同方向的视频流，
         *      因此，拉流端(本地SDK客户端)需要调整Activity的方向以显示不同方向的视频流；
         *      做法: 在 {@link IStreamListener#onRotation(int)} 中调用 {@link RotationModeActivity#setRotation(int)} ，
         *         在 {@link AppCompatActivity#onConfigurationChanged(Configuration)} 中调用 {@link VePhoneEngine#rotate(int)}。
         *
         * 2. PORTRAIT 模式下，推流端(云端实例)只会推送竖屏方向的视频流，
         *      拉流端(本地SDK客户端)无需调整Activity的方向。
         *      做法: 在 {@link IStreamListener#onRotation(int)} 和
         *          {@link AppCompatActivity#onConfigurationChanged(Configuration)} 中 都无需做任何事，注释掉相关代码即可。
         *          另外，需要将AndroidManifest.xml中该Activity的方向的设置为portrait。
         */
        mBuilder = new PhonePlayConfig.Builder();
        mBuilder.userId(userId)
                .ak(ak)
                .sk(sk)
                .token(token)
                .container(mContainer)
                .roundId(roundId)
                .podId(podId)
                .productId(productId)
                .rotation(Rotation.AUTO_ROTATION)
                .enableLocalKeyboard(false)
                .streamListener(this);

        mPhonePlayConfig = mBuilder.build();
        VePhoneEngine.getInstance().start(mPhonePlayConfig, this);
    }

    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        AcLog.d(TAG, "[onPlaySuccess] roundId " + roundId + " clarityId " + clarityId);
    }

    @Override
    public void onError(int i, String s) {
        AcLog.e(TAG, "[onError] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onWarning(int i, String s) {
        AcLog.w(TAG, "[onWarning] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onNetworkChanged(int i) {
        AcLog.d(TAG, "[onNetworkChanged] network: " + i);
    }

    @Override
    public void onServiceInit() {
        AcLog.d(TAG, "[onServiceInit]");
    }

    @Override
    public void onFirstAudioFrame(String s) {
        AcLog.d(TAG, "[onFirstAudioFrame] audioStreamId: " + s);
    }

    @Override
    public void onFirstRemoteVideoFrame(String s) {
        AcLog.d(TAG, "[onFirstRemoteVideoFrame] videoStreamId: " + s);
    }

    @Override
    public void onStreamStarted() {
        AcLog.d(TAG, "[onStreamStarted]");
    }

    @Override
    public void onStreamPaused() {
        AcLog.d(TAG, "[onStreamPaused]");
    }

    @Override
    public void onStreamResumed() {
        AcLog.d(TAG, "[onStreamResumed]");
    }

    @Override
    public void onStreamStats(StreamStats streamStats) {
        AcLog.d(TAG, "[onStreamStats] streamStats: " + streamStats);
    }

    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {
        AcLog.d(TAG, "[onLocalStreamStats] localStreamStats: " + localStreamStats);
    }

    @Override
    public void onStreamConnectionStateChanged(int i) {
        AcLog.d(TAG, "[onStreamConnectionStateChanged] connectionState: " + i);
    }

    @Override
    public void onDetectDelay(long l) {
        AcLog.d(TAG, "[onDetectDelay] detectDelay: " + l);
    }

    @Override
    public void onRotation(int i) {
        AcLog.d(TAG, "[onRotation] rotation: " + i);

        /**
         * AUTO_ROTATION 模式下，需要 调用该方法;
         * PORTRAIT 模式下，不需要 调用该方法。
         */
        setRotation(i);
    }

    @Override
    public void onPodExit(int i, String s) {
        AcLog.d(TAG, "[onPodExit] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onNetworkQuality(int i) {
        AcLog.d(TAG, "[onNetworkQuality] quality: " + i);
    }

    private void setRotation(int rotation) {
        switch (rotation) {
            case 0:
            case 180:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_PORTRAIT);
                break;
            case 90:
            case 270:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
                break;
        }
    }

}
