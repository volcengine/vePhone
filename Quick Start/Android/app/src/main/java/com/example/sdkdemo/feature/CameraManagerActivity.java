package com.example.sdkdemo.feature;

import android.content.res.Configuration;
import android.os.Bundle;
import android.view.Gravity;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.common.CameraVideoProvider;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.cloudcore.common.mode.CameraId;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamDescription;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamError;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamState;
import com.volcengine.cloudcore.common.mode.MirrorMode;
import com.volcengine.cloudcore.common.mode.StreamIndex;
import com.volcengine.cloudcore.common.mode.VideoSourceType;
import com.volcengine.cloudphone.apiservice.CameraManager;
import com.volcengine.cloudphone.apiservice.outinterface.CameraManagerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.cloudphone.apiservice.outinterface.RemoteCameraRequestListener;
import com.volcengine.cloudphone.base.VeVideoFrame;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 该类用于展示与相机{@link CameraManager}相关的功能接口
 */
public class CameraManagerActivity extends BasePlayActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "CameraManagerActivity";

    private ViewGroup mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
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
        initPhonePlayConfig();
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
        });
        mBtnSwitchFrontCamera.setOnClickListener(v -> {
            if (mCameraManager != null) {
                mCameraManager.switchCamera(CameraId.FRONT);
            }
        });
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

        mBuilder = new PhonePlayConfig.Builder();
        mBuilder.userId(userId)
                .ak(ak)
                .sk(sk)
                .token(token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(podId)
                .productId(productId)
                .streamListener(this);

        mPhonePlayConfig = mBuilder.build();
        VePhoneEngine.getInstance().start(mPhonePlayConfig, this);
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
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        AcLog.d(TAG, "[onConfigurationChanged] newConfig: " + newConfig.orientation);
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    /**
     * 播放成功回调
     *
     * @param roundId 当次会话生命周期标识符
     * @param clarityId 当前画面的清晰度，首帧渲染到画面时触发该回调
     */
    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        AcLog.d(TAG, "[onPlaySuccess] roundId " + roundId + " clarityId " + clarityId);
    }

    /**
     * SDK内部产生的错误回调
     *
     * @param errorCode 错误码
     * @param errorMessage 错误详情
     */
    @Override
    public void onError(int errorCode, String errorMessage) {
        AcLog.e(TAG, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage);
        Toast.makeText(this, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage, Toast.LENGTH_SHORT).show();
    }

    /**
     * SDK内部产生的警告回调
     *
     * @param warningCode 警告码
     * @param warningMessage 警告详情
     */
    @Override
    public void onWarning(int warningCode, String warningMessage) {
        AcLog.d(TAG, "[onWarning] warningCode: " + warningCode + ", warningMessage: " + warningMessage);
    }

    /**
     * 网络连接类型和状态切换回调
     *
     * @param networkType 当前的网络类型
     *         -1 -- 网络连接类型未知
     *          0 -- 网络连接已断开
     *          1 -- 网络类型为 LAN
     *          2 -- 网络类型为 Wi-Fi（包含热点）
     *          3 -- 网络类型为 2G 移动网络
     *          4 -- 网络类型为 3G 移动网络
     *          5 -- 网络类型为 4G 移动网络
     *          6 -- 网络类型为 5G 移动网络
     */
    @Override
    public void onNetworkChanged(int networkType) {
        AcLog.d(TAG, "[onNetworkChanged] networkType: " + networkType);
    }

    /**
     * 即将废弃，建议使用{@link IPlayerListener#onServiceInit(Map)}
     */
    @Override
    public void onServiceInit() {

    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        AcLog.d(TAG, "[onServiceInit] extras: " + extras);
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
                    AcLog.i(TAG, "[onLocalVideoStateChanged] localVideoStreamState: " +
                            localVideoStreamState + ", localVideoStreamError: " + localVideoStreamError);
                }

                /**
                 * 本地首帧被采集回调
                 */
                @Override
                public void onFirstCapture() {
                    AcLog.i(TAG, "[onFirstCapture]");
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
                    AcLog.i(TAG, "[onVideoStreamStartRequested] cameraId: " + cameraId);
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
//                    if (mCameraVideoProvider != null) {
//                        mCameraManager.setVideoSourceType(StreamIndex.MAIN, VideoSourceType.EXTERNAL);
//                        mCameraVideoProvider.setFrameConsumer( veVideoFrame -> {
//                            mCameraManager.pushExternalVideoFrame(StreamIndex.MAIN, veVideoFrame);
//                        });
//                        mCameraVideoProvider.start(cameraId); // 开始视频采集
//                        mCameraManager.publishLocalVideo();
//                    }
                }

                /**
                 * 云端请求关闭本地摄像头回调
                 */
                @Override
                public void onVideoStreamStopRequested() {
                    AcLog.i(TAG, "[onVideoStreamStopRequested]");
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
    }

    /**
     * 收到音频首帧时的回调
     *
     * @param audioStreamId 远端实例音频流的ID
     */
    @Override
    public void onFirstAudioFrame(String audioStreamId) {
        AcLog.d(TAG, "[onFirstAudioFrame] audioStreamId: " + audioStreamId);
    }

    /**
     * 收到视频首帧时的回调
     *
     * @param videoStreamId 远端实例视频流的ID
     */
    @Override
    public void onFirstRemoteVideoFrame(String videoStreamId) {
        AcLog.d(TAG, "[onFirstRemoteVideoFrame] videoStreamId: " + videoStreamId);
    }

    /**
     * 开始播放的回调
     */
    @Override
    public void onStreamStarted() {
        AcLog.d(TAG, "[onStreamStarted]");
    }

    /**
     * 暂停播放后的回调，调用{@link VePhoneEngine#pause()}后会触发
     */
    @Override
    public void onStreamPaused() {
        AcLog.d(TAG, "[onStreamPaused]");
    }

    /**
     * 恢复播放后的回调，调用{@link VePhoneEngine#resume()} 或 VePhoneEngine#muteAudio(false) 后会触发
     */
    @Override
    public void onStreamResumed() {
        AcLog.d(TAG, "[onStreamResumed]");
    }

    /**
     * 周期为2秒的音视频网络状态的回调，可用于内部数据分析或监控
     *
     * @param streamStats 远端视频流的性能状态
     */
    @Override
    public void onStreamStats(StreamStats streamStats) {
        AcLog.d(TAG, "[onStreamStats] streamStats: " + streamStats);
    }

    /**
     * 周期为2秒的本地推送的音视频流的状态回调
     *
     * @param localStreamStats 本地音视频流的性能状态
     */
    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {
        AcLog.d(TAG, "[onLocalStreamStats] localStreamStats: " + localStreamStats);
    }

    /**
     * 视频流连接状态变化
     *
     * @param state 视频流连接状态
     *              1 -- 连接断开
     *              2 -- 首次连接，正在连接中
     *              3 -- 首次连接成功
     *              4 -- 连接断开后，重新连接中
     *              5 -- 连接断开后，重新连接成功
     *              6 -- 连接断开超过10秒，但仍然会继续连接
     *              7 -- 连接失败，不会继续连接
     */
    @Override
    public void onStreamConnectionStateChanged(int state) {
        AcLog.d(TAG, "[onStreamConnectionStateChanged] connectionState: " + state);
    }

    /**
     * 操作延迟回调
     *
     * @param elapse 操作延迟的具体值，单位:毫秒
     */
    @Override
    public void onDetectDelay(long elapse) {
        AcLog.d(TAG, "[onDetectDelay] detectDelay: " + elapse);
    }

    /**
     * 客户端的旋转回调
     *
     * 远端实例通过该回调向客户端发送视频流的方向(横屏或竖屏)，为保证视频流方向与Activity方向一致，
     * 需要在该回调中根据rotation参数，调用 {@link BasePlayActivity#setRotation(int)} 来调整Activity的方向，
     * 0/180需将Activity调整为竖屏，90/270则将Activity调整为横屏；
     * 同时，需要在 {@link MessageChannelActivity#onConfigurationChanged(Configuration)} 回调中，
     * 根据当前Activity的方向，调用 {@link VePhoneEngine#rotate(int)} 来调整视频流的方向。
     *
     * @param rotation 旋转方向
     *          0, 180 -- 竖屏
     *         90, 270 -- 横屏
     */
    @Override
    public void onRotation(int rotation) {
        AcLog.d(TAG, "[onRotation] rotation: " + rotation);
        setRotation(rotation);
    }

    /**
     * 远端实例退出回调
     *
     * @param reasonCode 退出的原因码
     * @param reasonMessage 退出的原因详情
     */
    @Override
    public void onPodExit(int reasonCode, String reasonMessage) {
        AcLog.d(TAG, "[onPodExit] reasonCode: " + reasonCode + ", reasonMessage: " + reasonMessage);
    }

    /**
     * 周期为2秒的游戏中的网络质量回调
     *
     * @param quality 网络质量评级
     *                0 -- 网络状况未知，无法判断网络质量
     *                1 -- 网络状况极佳，能够高质量承载当前业务
     *                2 -- 当前网络状况良好，能够较好地承载当前业务
     *                3 -- 当前网络状况有轻微劣化，但不影响正常使用
     *                4 -- 当前网络质量欠佳，会影响当前业务的主观体验
     *                5 -- 当前网络已经无法承载当前业务的媒体流，需要采取相应策略，
     *                      比如降低媒体流的码率或者更换网络
     *                6 -- 当前网络完全无法正常通信
     */
    @Override
    public void onNetworkQuality(int quality) {
        AcLog.d(TAG, "[onNetworkQuality] quality: " + quality);
    }
}
