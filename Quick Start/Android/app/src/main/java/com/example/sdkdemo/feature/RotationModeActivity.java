package com.example.sdkdemo.feature;

import android.content.res.Configuration;
import android.os.Bundle;
import android.view.ViewGroup;
import android.view.WindowManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudcore.common.mode.VideoRotationMode;
import com.volcengine.cloudphone.apiservice.VideoRenderModeManager;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Map;


/**
 * 该类用于展示与Rotation相关的功能接口的使用方法
 * Rotation有三种模式：
 * 自动旋转模式(默认){@link Rotation#AUTO_ROTATION}、
 * 竖屏模式{@link Rotation#PORTRAIT}、
 * 竖屏模式(暂不可用){@link Rotation#PORTRAIT}
 *
 * 使用竖屏模式{@link Rotation#PORTRAIT}可以实现一种场景：
 * 横屏应用竖屏显示，即：本地Activity的方向始终为竖屏，即使云端实例的应用是横屏显示。
 *
 * 另外，在RotationMode设置为自动旋转(默认){@link Rotation#AUTO_ROTATION}时，
 * 需要通过视频旋转模式{@link VideoRotationMode}来判断如何进行处理。
 *
 * 目前支持的渲染模式有两种:
 * 外部旋转模式(默认){@link VideoRotationMode#EXTERNAL}、
 * 内部旋转模式{@link VideoRotationMode#INTERNAL}
 * 外部旋转模式需要在{@link IStreamListener#onRotation(int)}自行处理旋转逻辑；
 * 内部旋转模式则由SDK内部处理，用户无需做任何处理。
 */
public class RotationModeActivity extends BasePlayActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "RotationModeActivity";

    private ViewGroup mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
    private Rotation mRotation = Rotation.AUTO_ROTATION;
    private int mVideoRotationMode = VideoRotationMode.EXTERNAL;


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
         * AUTO_ROTATION 模式下，且使用[外部视频旋转]，需要 调用该方法;
         * AUTO_ROTATION 模式下，且使用[内部视频旋转]，不需要 调用该方法;
         * PORTRAIT 模式下，不需要 调用该方法。
         */
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
    }

    private void initPhonePlayConfig() {
        /**
         * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
         * ak/sk/token用于用户鉴权，需要从火山官网上获取，具体步骤详见README[鉴权相关]。
         * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
         *
         * ak/sk/token/podId的值从assets目录下的sts.json文件中读取，该目录及文件需要自行创建。
         * sts.json的格式形如
         * {
         *     "podId": "your_pod_id",
         *     "productId": "your_product_id",
         *     "ak": "your_ak",
         *     "sk": "your_sk",
         *     "token": "your_token"
         * }
         */
        String ak = "", sk = "", token = "", podId = "", productId = "";  // 这里需要替换成你的 ak/sk/token/podId/productId
        String sts = AssetsUtil.getTextFromAssets(this.getApplicationContext(), "sts.json");
        try {
            JSONObject stsJObj = new JSONObject(sts);
            ak = stsJObj.getString("ak");
            sk = stsJObj.getString("sk");
            token = stsJObj.getString("token");
            podId = stsJObj.getString("podId");
            productId = stsJObj.getString("productId");
        } catch (JSONException e) {
            e.printStackTrace();
        }

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
         *      但是，如果设置视频旋转模式为内部旋转，SDK内部会对旋转做任何处理，用户无需做任何操作。
         *
         * 2. PORTRAIT 模式下，推流端(云端实例)只会推送竖屏方向的视频流，
         *      拉流端(本地SDK客户端)无需调整Activity的方向。
         *      做法: 在 {@link IStreamListener#onRotation(int)} 和
         *          {@link AppCompatActivity#onConfigurationChanged(Configuration)} 中 都无需任何操作，注释掉相关代码即可。
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
                .rotation(mRotation)
                .videoRotationMode(mVideoRotationMode)
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

    /**
     * 即将废弃，建议使用{@link IPlayerListener#onServiceInit(Map)}
     */
    @Deprecated
    @Override
    public void onServiceInit() {

    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        AcLog.d(TAG, "[onServiceInit] extras: " + extras);
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
    public void onRotation(int rotation) {
        AcLog.d(TAG, "[onRotation] rotation: " + rotation);

        /**
         * AUTO_ROTATION 模式下，且使用[外部视频旋转]，需要 调用该方法;
         * AUTO_ROTATION 模式下，且使用[内部视频旋转]，不需要 调用该方法;
         * PORTRAIT 模式下，不需要 调用该方法。
         */
//        setRotation(rotation);

        VideoRenderModeManager videoRenderModeManager = VePhoneEngine.getInstance().getVideoRenderModeManager();
        if (videoRenderModeManager != null) {
            /**
             * 获取当前的视频旋转模式
             * int getVideoRotationMode()
             *
             * @return 0 -- 外部旋转模式
             *         1 -- 内部旋转模式
             */
            if (videoRenderModeManager.getVideoRotationMode() == VideoRotationMode.EXTERNAL) {
                if (mRotation.equals(Rotation.AUTO_ROTATION)) {
                    // 外部旋转模式，需要在onRotation回调中处理Activity的方向
                    setRotation(rotation);
                }
                else {
                    // 横屏应用竖屏显示，不需要处理任何逻辑
                }
            }
            else if (videoRenderModeManager.getVideoRotationMode() == VideoRotationMode.INTERNAL) {
                // 内部旋转模式，不需要处理任何逻辑
            }
        }
        else {
            AcLog.e(TAG, "mVideoRenderModeManager == null");
        }
    }

    @Override
    public void onPodExit(int i, String s) {
        AcLog.d(TAG, "[onPodExit] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onNetworkQuality(int i) {
        AcLog.d(TAG, "[onNetworkQuality] quality: " + i);
    }

}
