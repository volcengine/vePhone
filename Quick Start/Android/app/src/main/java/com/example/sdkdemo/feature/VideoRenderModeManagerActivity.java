package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.VideoRenderMode;
import com.volcengine.cloudcore.common.mode.VideoRotationMode;
import com.volcengine.cloudphone.apiservice.VideoRenderModeManager;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与视频渲染模式{@link VideoRenderModeManager}相关的功能接口的使用方法
 * 目前支持的渲染模式有三种:
 * 等比缩放居中模式(默认){@link VideoRenderMode#VIDEO_RENDER_MODE_FIT}、
 * 非等比拉伸模式{@link VideoRenderMode#VIDEO_RENDER_MODE_FILL}、
 * 等比缩放模式{@link VideoRenderMode#VIDEO_RENDER_MODE_COVER}
 *
 * 该功能需配合{@link PhonePlayConfig.Builder#remoteWindowSize(int, int)}使用。
 * 对于情况二和情况三，渲染模式切换有效；对于情况一和其他情况，渲染模式切换无效。
 *
 * remoteWindowSize(int width, int height) 设置云端推流宽高比，取值范围: width>=0、height>=0。
 * 情况一：如果不使用remoteWindowSize传入宽高比，默认使用初始化时Container的宽高比作为请求参数上传；
 * 情况二：如果传入的width = 0、height = 0，云端按照实例屏幕的原始画面宽高进行推流；
 * 情况三：如果传入的width > 0、height > 0，云端按照指定的宽高比进行推流(如果云端实例屏幕为竖屏，指定的width必须小于height)；
 * 其他情况：同情况一。
 *
 */
public class VideoRenderModeManagerActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private VideoRenderModeManager mVideoRenderModeManager;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnFitMode, mBtnFillMode, mBtnCoverMode;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_video_render_mode);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnFitMode = findViewById(R.id.btn_fit_mode);
        mBtnFillMode = findViewById(R.id.btn_fill_mode);
        mBtnCoverMode = findViewById(R.id.btn_cover_mode);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnFitMode.setOnClickListener(view -> {
            /**
             * 更新渲染模式
             * int updateVideoRenderMode(int renderMode)
             *
             * @param renderMode 渲染模式
             *
             * @return 0 -- 调用成功
             *         < 0 -- 调用失败
             */
            if (mVideoRenderModeManager != null) {
                mVideoRenderModeManager.updateVideoRenderMode(VideoRenderMode.VIDEO_RENDER_MODE_FIT);
            }
            else {
                Log.e(TAG, "mVideoRenderModeManager == null");
            }
        });
        mBtnFillMode.setOnClickListener(view -> {
            VePhoneEngine.getInstance().resume();
            if (mVideoRenderModeManager != null) {
                mVideoRenderModeManager.updateVideoRenderMode(VideoRenderMode.VIDEO_RENDER_MODE_FILL);
            }
            else {
                Log.e(TAG, "mVideoRenderModeManager == null");
            }
        });
        mBtnCoverMode.setOnClickListener(v -> {
            if (mVideoRenderModeManager != null) {
                mVideoRenderModeManager.updateVideoRenderMode(VideoRenderMode.VIDEO_RENDER_MODE_COVER);
            }
            else {
                Log.e(TAG, "mVideoRenderModeManager == null");
            }
        });

    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(SdkUtil.getClientUid())
                            .ak(auth.ak)
                            .sk(auth.sk)
                            .token(auth.token)
                            .container(mContainer)
                            .remoteWindowSize(0, 0)
                            .enableLocalKeyboard(true)
                            .rotation(Rotation.AUTO_ROTATION)
                            .videoRotationMode(VideoRotationMode.INTERNAL)
                            .roundId(SdkUtil.getRoundId())
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .streamListener(this);
                    VePhoneEngine.getInstance().start(builder.build(), this);
                },
                p -> {
                    showTipDialog(MessageFormat.format(getString(R.string.invalid_phone_play_config) , p));
                });
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
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mVideoRenderModeManager = VePhoneEngine.getInstance().getVideoRenderModeManager();
    }

}
