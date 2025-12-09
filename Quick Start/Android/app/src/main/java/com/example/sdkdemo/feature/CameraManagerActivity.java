package com.example.sdkdemo.feature;

import android.Manifest;
import android.annotation.SuppressLint;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.CameraVideoProvider;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudcore.common.mode.CameraId;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamDescription;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamError;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamState;
import com.volcengine.cloudcore.common.mode.MirrorMode;
import com.volcengine.cloudphone.apiservice.CameraManager;
import com.volcengine.cloudphone.apiservice.outinterface.CameraManagerListener;
import com.volcengine.cloudphone.apiservice.outinterface.RemoteCameraRequestListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 该类用于展示与相机{@link CameraManager}相关的功能接口
 * 使用该服务可以实现云端实例对本地视频的采集，采集方式包括内部采集与外部采集。
 * 内部采集使用本地摄像头等设备进行视频采集，不进行加工处理直接发送给云端实例；
 * 外部采集可以对本地采集的视频进行一定的加工处理，再发送给云端实例。
 */
public class CameraManagerActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    CameraManager mCameraManager;
    private SwitchCompat mSwShowOrHide, mSwEnableMirror;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnAddLocalCanvas, mBtnPushMultipleStream, mBtnSwitchFrontCamera, mBtnSwitchRearCamera;
    private CameraVideoProvider mCameraVideoProvider;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_camera);
        initView();
        initPlayConfigAndStartPlay();
        mCameraVideoProvider = new CameraVideoProvider(getApplicationContext());
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mSwEnableMirror = findViewById(R.id.sw_enable_mirror);
        mBtnAddLocalCanvas = findViewById(R.id.btn_add_local_canvas);
        mBtnPushMultipleStream = findViewById(R.id.btn_push_multiple_streams);
        mBtnSwitchFrontCamera = findViewById(R.id.btn_switch_front_camera);
        mBtnSwitchRearCamera = findViewById(R.id.btn_switch_rear_camera);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnAddLocalCanvas.setOnClickListener(v -> {
            FrameLayout view = findViewById(R.id.fl_local_canvas);
            SurfaceView surfaceView = new SurfaceView(this);
            FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
            params.gravity = Gravity.CENTER;
            surfaceView.setZOrderOnTop(true);
            view.addView(surfaceView, params);
            if (mCameraManager != null) {
                mCameraManager.setLocalVideoCanvas(surfaceView);
            }
            else {
                Log.e(TAG, "mCameraManager == null");
            }
        });

        /**
         * setLocalVideoMirrorMode(MirrorMode mode) -- 设置是否镜像翻转本地摄像头画面
         *
         * @param mode 镜像翻转模式
         *             MIRROR_MODE_OFF(0) -- 不开启镜像翻转
         *             MIRROR_MODE_ON(1) -- 开启镜像翻转
         */
        mSwEnableMirror.setOnCheckedChangeListener((compoundButton, b) -> {
            if (mCameraManager != null) {
                mCameraManager.setLocalVideoMirrorMode(
                        b ? MirrorMode.MIRROR_MODE_ON : MirrorMode.MIRROR_MODE_OFF);
            }
            else {
                Log.e(TAG, "mCameraManager == null");
            }
        });

        /**
         * setVideoEncoderConfig(List<VideoStreamDescription> videoStreamDescriptions) -- 设置本地视频编码质量策略
         *
         * @param videoStreamDescriptions 视频编码质量参数列表
         *                                参数包括width(宽度), height(高度), frameRate(帧率), maxBitrate(最大码率)
         */
        mBtnPushMultipleStream.setOnClickListener(v -> {
            List<LocalVideoStreamDescription> list = new ArrayList<>();
            list.add(new LocalVideoStreamDescription(1920, 1080, 30, 5000, 5000));
            list.add(new LocalVideoStreamDescription(1420, 720, 20, 3000, 3000));
            list.add(new LocalVideoStreamDescription(1000, 500, 20, 2000, 2000));
            if (mCameraManager != null) {
                mCameraManager.setVideoEncoderConfig(list);
            }
            else {
                Log.e(TAG, "mCameraManager == null");
            }
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
        mBtnSwitchRearCamera.setOnClickListener(v -> {
            if (mCameraManager != null) {
                mCameraManager.switchCamera(CameraId.BACK);
            }
            else {
                Log.e(TAG, "mCameraManager == null");
            }
        });
        mBtnSwitchFrontCamera.setOnClickListener(v -> {
            if (mCameraManager != null) {
                mCameraManager.switchCamera(CameraId.FRONT);
            }
            else {
                Log.e(TAG, "mCameraManager == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        String roundId = "roundId_123";
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        builder.userId(SdkUtil.getClientUid())
                .ak(auth.ak)
                .sk(auth.sk)
                .token(auth.token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(auth.podId)
                .productId(auth.productId)
                .streamListener(this);
        VePhoneEngine.getInstance().start(builder.build(), this);
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
        if (mCameraVideoProvider != null) {
            mCameraVideoProvider.stop();
            mCameraVideoProvider = null;
        }
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mCameraManager = VePhoneEngine.getInstance().getCameraManager();
        if (mCameraManager != null) {
            /**
             * setCameraManagerListener(CameraManagerListener listener) -- 设置本地摄像头推流状态监听器
             */
            mCameraManager.setCameraManagerListener(new CameraManagerListener() {
                /**
                 * 本地摄像头推流状态改变回调
                 *
                 * @param localVideoStreamState 当前推流状态
                 * @param localVideoStreamError 推流状态错误码
                 */
                @Override
                public void onLocalVideoStateChanged(LocalVideoStreamState localVideoStreamState, LocalVideoStreamError localVideoStreamError) {
                    Log.i(TAG, "[onLocalVideoStateChanged] localVideoStreamState: " +
                            localVideoStreamState + ", localVideoStreamError: " + localVideoStreamError);
                }

                /**
                 * 本地首帧被采集回调
                 */
                @Override
                public void onFirstCapture() {
                    Log.i(TAG, "[onFirstCapture]");
                }
            });

            /**
             * setRemoteRequestListener(RemoteCameraRequestListener listener) -- 设置云端请求打开或者关闭本地摄像头的监听器
             */
            mCameraManager.setRemoteRequestListener(new RemoteCameraRequestListener() {
                /**
                 * 云端请求打开本地摄像头回调
                 *
                 * @param cameraId 摄像头ID
                 *                 FRONT(0) -- 前置
                 *                 BACK(1) -- 后置
                 */
                @Override
                public void onVideoStreamStartRequested(CameraId cameraId) {
                    Log.i(TAG, "[onVideoStreamStartRequested] cameraId: " + cameraId);
                    requestPermissionAndStartSendVideo(cameraId);
                }

                /**
                 * 云端请求关闭本地摄像头回调
                 */
                @Override
                public void onVideoStreamStopRequested() {
                    Log.i(TAG, "[onVideoStreamStopRequested]");
                    /**
                     * (内部采集使用)
                     * stopVideoStream -- 停止推流，建议在onVideoStreamStopRequested中调用
                     */
                    mCameraManager.stopVideoStream();

                    /**
                     * (外部采集使用)
                     * 取消发布本地视频，视频外部采集需要调用此接口
                     * int unpublishLocalVideo()
                     *
                     * @return 0 -- 调用成功
                     *        -1 -- 调用失败
                     */
//                    if (mCameraVideoProvider != null) {
//                        mCameraVideoProvider.stop(); // 停止视频采集
//                        mCameraManager.unpublishLocalVideo();
//                    }
                }
            });
        }
        else {
            Log.e(TAG, "mCameraManager == null");
        }
    }


    private void requestPermissionAndStartSendVideo(CameraId cameraId) {
        PermissionUtils.permission(Manifest.permission.CAMERA)
                .callback(new PermissionUtils.SimpleCallback() {
                    @SuppressLint("MissingPermission")
                    @Override
                    public void onGranted() {
                        /**
                         * (内部采集使用)
                         * startVideoStream -- 开始指定摄像头采集兵推流，建议在onVideoStreamStartRequested中调用
                         *
                         * @return 0 -- 调用成功
                         *        -1 -- 调用失败
                         */
                        mCameraManager.startVideoStream(cameraId);

                        /**
                         * (外部采集使用)
                         * 设置本地视频源类型
                         * int setVideoSourceType(int index, int type)
                         *
                         * @param index 视频流索引
                         *              0 -- 主流
                         *              1 -- 屏幕流
                         * @param type 视频源类型
                         *             0 -- 外部采集视频源(自定义采集)
                         *             1 -- 内部采集视频源(本地相机采集)
                         *
                         * @return 0 -- 调用成功
                         *        -1 -- 调用失败
                         *
                         *
                         * 向云端实例推送外部采集视频源(需要先调用 setVideoSourceType，将采集模式设置为外部采集视频源，然后调用 publishLocalVideo 发布本地视频)
                         * int pushExternalVideoFrame(int index, VeVideoFrame frame)
                         *
                         * @param index 视频流索引
                         * @param frame 外部采集的视频帧
                         *
                         * @return 0 -- 调用成功
                         *        -1 -- 调用失败
                         *
                         * 发布本地视频，视频外部采集需要调用此接口
                         * int publishLocalVideo()
                         *
                         * @return 0 -- 调用成功
                         *        -1 -- 调用失败
                         */
//                        if (mCameraVideoProvider != null) {
//                            mCameraManager.setVideoSourceType(StreamIndex.MAIN, VideoSourceType.EXTERNAL);
//                            mCameraVideoProvider.setFrameConsumer( veVideoFrame -> {
//                                mCameraManager.pushExternalVideoFrame(StreamIndex.MAIN, veVideoFrame);
//                            });
//                            mCameraVideoProvider.start(cameraId); // 开始视频采集
//                            mCameraManager.publishLocalVideo();
//                        }
                    }

                    @Override
                    public void onDenied() {
                        showToast("无相机权限");
                    }
                }).request();
    }

}
