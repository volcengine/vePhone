package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.ViewGroup;
import android.view.WindowManager;

import androidx.annotation.Nullable;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.androidcloud.common.model.RotationState;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.VideoRotationMode;
import com.volcengine.cloudphone.apiservice.VideoRenderModeManager;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;


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
 * 外部旋转模式需要在{@link IStreamListener#onRotation(RotationState)}自行处理旋转逻辑；
 * 内部旋转模式则由SDK内部处理，用户无需做任何处理。
 */
public class RotationModeActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private Rotation mRotation = Rotation.AUTO_ROTATION;
    private int mVideoRotationMode = VideoRotationMode.EXTERNAL;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_rotation_mode);
        initView();
        initPlayConfigAndStartPlay();
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

    private void initView() {
        mContainer = findViewById(R.id.container);
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        /*
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
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(SdkUtil.getClientUid())
                            .ak(auth.ak)
                            .sk(auth.sk)
                            .token(auth.token)
                            .container(mContainer)
                            .roundId(SdkUtil.getRoundId())
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .rotation(mRotation)
                            .videoRotationMode(mVideoRotationMode)
                            .enableLocalKeyboard(false)
                            .streamListener(this);
                    VePhoneEngine.getInstance().start(builder.build(), this);
                },
                p -> {
                    showTipDialog(MessageFormat.format(getString(R.string.invalid_phone_play_config) , p));
                });
    }


    @Override
    public void onRotation(RotationState state) {
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
                super.onRotation(state);
            }
            else if (videoRenderModeManager.getVideoRotationMode() == VideoRotationMode.INTERNAL) {
                // 内部旋转模式，不需要处理任何逻辑
            }
        }
        else {
            Log.e(TAG, "mVideoRenderModeManager == null");
        }
    }

}
