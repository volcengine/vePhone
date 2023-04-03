package com.example.sdkdemo.feature;

import android.content.Context;
import android.view.Gravity;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ScrollView;

import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudcore.common.mode.CameraId;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamDescription;
import com.volcengine.cloudcore.common.mode.MirrorMode;
import com.volcengine.cloudphone.apiservice.CameraManager;

import java.util.ArrayList;
import java.util.List;

public class CamaraManagerView {

    private final CameraManager mCameraManager;
    private static final String TAG = "CamaraManager";
    private DialogUtils.DialogWrapper mDialogWrapper;

    public CamaraManagerView(Context context, CameraManager cameraManager, Button button) {
        this.mCameraManager = cameraManager;
        mDialogWrapper  = DialogUtils.wrapper(new CamaraManagerView.TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends ScrollView {

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_camera, this);
            setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            findViewById(R.id.btn_add_camera_canvas).setOnClickListener(v -> {
                FrameLayout view = findViewById(R.id.fm_local_canvas);
                SurfaceView surfaceView = new SurfaceView(context);
                FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
                params.gravity = Gravity.CENTER;
                surfaceView.setZOrderOnTop(true);
                view.addView(surfaceView, params);
                mCameraManager.setLocalVideoCanvas(surfaceView);
            });

            /**
             * setLocalVideoMirrorMode(MirrorMode mode) -- 设置是否镜像翻转本地摄像头画面
             *
             * @param mode 镜像翻转模式
             *             MIRROR_MODE_OFF(0) -- 不开启镜像翻转
             *             MIRROR_MODE_ON(1) -- 开启镜像翻转
             */
            SwitchCompat switchCompat = findViewById(R.id.switch_enable_mirror);
            switchCompat.setChecked(false);
            switchCompat.setOnCheckedChangeListener((compoundButton, b) ->
                    mCameraManager.setLocalVideoMirrorMode(b ? MirrorMode.MIRROR_MODE_ON : MirrorMode.MIRROR_MODE_OFF)
            );

            /**
             * setVideoEncoderConfig(List<VideoStreamDescription> videoStreamDescriptions) -- 设置本地视频编码质量策略
             *
             * @param videoStreamDescriptions 视频编码质量参数列表
             *                                参数包括width(宽度), height(高度), frameRate(帧率), maxBitrate(最大码率)
             */
            findViewById(R.id.btn_publish_stream).setOnClickListener(v -> {
                List<LocalVideoStreamDescription> list = new ArrayList<>();
                list.add(new LocalVideoStreamDescription(1920, 1080, 30, 5000));
                list.add(new LocalVideoStreamDescription(1420, 720, 20, 3000));
                list.add(new LocalVideoStreamDescription(1000, 500, 20, 2000));
                mCameraManager.setVideoEncoderConfig(list);
            });

            /**
             * switchCamera(CameraId cameraId) -- 切换前后摄像头
             *
             * @param cameraId 摄像头ID
             *                 FRONT(0) -- 前置
             *                 BACK(1) -- 后置
             * @return 0 -- 调用成功
             *        -1 -- 调用失败
             */
            findViewById(R.id.btn_check_camera_back).setOnClickListener(v -> {
                mCameraManager.switchCamera(CameraId.BACK);
            });
            findViewById(R.id.btn_check_camera_front).setOnClickListener(v -> {
                mCameraManager.switchCamera(CameraId.FRONT);
            });
        }
    }
}
