package com.example.sdkdemo;

import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT;

import static com.example.sdkdemo.util.Feature.FEATURE_AUDIO;
import static com.example.sdkdemo.util.Feature.FEATURE_CAMERA;
import static com.example.sdkdemo.util.Feature.FEATURE_CLIPBOARD;
import static com.example.sdkdemo.util.Feature.FEATURE_FILE_CHANNEL;
import static com.example.sdkdemo.util.Feature.FEATURE_FILE_EXCHANGE;
import static com.example.sdkdemo.util.Feature.FEATURE_LOCAL_INPUT;
import static com.example.sdkdemo.util.Feature.FEATURE_LOCATION;
import static com.example.sdkdemo.util.Feature.FEATURE_MESSAGE_CHANNEL;
import static com.example.sdkdemo.util.Feature.FEATURE_PAD_CONSOLE;
import static com.example.sdkdemo.util.Feature.FEATURE_POD_CONTROL;
import static com.example.sdkdemo.util.Feature.FEATURE_SENSOR;
import static com.example.sdkdemo.util.Feature.FEATURE_UNCLASSIFIED;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.res.Configuration;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.constraintlayout.widget.ConstraintLayout;

import com.example.sdkdemo.feature.AudioServiceView;
import com.example.sdkdemo.feature.CameraManagerView;
import com.example.sdkdemo.feature.ClarityServiceView;
import com.example.sdkdemo.feature.ClipBoardServiceManagerView;
import com.example.sdkdemo.feature.FileChannelView;
import com.example.sdkdemo.feature.FileExchangeView;
import com.example.sdkdemo.feature.LocalInputManagerView;
import com.example.sdkdemo.feature.LocationServiceView;
import com.example.sdkdemo.feature.MessageChannelView;
import com.example.sdkdemo.feature.PadConsoleManagerView;
import com.example.sdkdemo.feature.PodControlServiceView;
import com.example.sdkdemo.feature.SensorView;
import com.example.sdkdemo.feature.UnclassifiedView;
import com.example.sdkdemo.util.AssetsUtil;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.cloudcore.common.mode.CameraId;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamError;
import com.volcengine.cloudcore.common.mode.LocalVideoStreamState;
import com.volcengine.cloudphone.apiservice.IClipBoardListener;
import com.volcengine.cloudphone.apiservice.StreamProfileChangeCallBack;
import com.volcengine.cloudphone.apiservice.outinterface.CameraManagerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.cloudphone.apiservice.outinterface.RemoteCameraRequestListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

public class PhoneActivity extends AppCompatActivity implements IPlayerListener, IStreamListener {

    private final String TAG = getClass().getSimpleName();
    private ViewGroup mContainer;
    public static final String KEY_POD_ID = "podId";
    public static final String KEY_PRODUCT_ID = "productId";
    public static final String KEY_ROUND_ID = "roundId";
    public static final String KEY_ClARITY_ID = "clarityId";
    public static final String KEY_FEATURE_ID = "featureId";
    private ConstraintLayout mContainers;

    private boolean mIsHideButtons = false;
    public VePhoneEngine vePhoneEngine = VePhoneEngine.getInstance();
    DialogUtils.DialogWrapper mDialogWrapper;
    FileChannelView mFileChannelView;
    private PhonePlayConfig mPhonePlayConfig;

    private Button btnAudio, btnCamera, btnClarity, btnClipBoard, btnFileChannel, btnLocation;
    private Button btnMessageChannel, btnPodControl, btnRotation, btnSensor, btnUnclassified;
    private Button btnLocalInput, btnPadConsole, btnFileExchange, btnGround;
    private TextView tvInfo;
    private boolean isLand = false;
    private boolean isShowInfo = false;
    private long lastBackPress;

    private String podId, productId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_play);
        mContainer = findViewById(R.id.container);
        initView();
        initConfig();
    }

    private void initConfig() {
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        String userId = "userid" + System.currentTimeMillis();
        AcLog.d(TAG, "userId: " + userId);
        Intent intent = getIntent();
        podId = intent.getStringExtra(KEY_POD_ID);
        productId = intent.getStringExtra(KEY_PRODUCT_ID);

        /**
         * ak/sk/token的值从assets目录下的sts.json文件中读取，该目录及文件需要自行创建。
         * sts.json的格式形如
         * {
         *     "ak": "your_ak",
         *     "sk": "your_sk",
         *     "token": "your_token"
         * }
         */
        String ak = "", sk = "", token = "";  // 这里需要替换成你的 ak/sk/token
        String sts = AssetsUtil.getTextFromAssets(this.getApplicationContext(), "sts.json");
        try {
            JSONObject stsJObj = new JSONObject(sts);
            ak = stsJObj.getString("ak");
            sk = stsJObj.getString("sk");
            token = stsJObj.getString("token");

        } catch (JSONException e) {
            e.printStackTrace();
        }


        // ak, sk, token: 请通过火山引擎申请ak获得，详情见https://www.volcengine.com/docs/6512/75577
        builder.userId(userId) // 用户userid
                .ak(ak) // 必填 ACEP ak
                .sk(sk)  // 必填 ACEP sk
                .token(token) // 必填 ACEP token
                .container(mContainer) // 必填参数，用来承载画面的 Container, 参数说明: layout 需要是FrameLayout或者FrameLayout的子类
                .podId(podId) // 必填参数，实例id
                .productId(productId) // 必填参数，业务id
                .roundId(intent.getStringExtra(KEY_ROUND_ID)) // 必填参数，自定义roundId
                .videoStreamProfileId(intent.getIntExtra(KEY_ClARITY_ID, 1)) // 选填参数，清晰度ID
                .enableGravitySensor(true)
                .enableGyroscopeSensor(true)
                .enableMagneticSensor(true)
                .enableOrientationSensor(true)
                .enableVibrator(true)
                .enableLocationService(true)
                .enableLocalKeyboard(true)
                .enableFileChannel(true)
                .streamListener(PhoneActivity.this);

        mPhonePlayConfig = builder.build();
        // 初始化成功才可以调用
        vePhoneEngine.start(mPhonePlayConfig, PhoneActivity.this);
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        outState.putString("key_uid", "user_id");
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onResume() {
        super.onResume();
        vePhoneEngine.resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        vePhoneEngine.pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        if (mDialogWrapper != null) {
            mDialogWrapper.release();
            mDialogWrapper = null;
        }
        if (mFileChannelView != null) {
            mFileChannelView = null;
        }
        super.onDestroy();
    }

    @Override
    public void finish() {
        vePhoneEngine.stop();
        super.finish();
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (mFileChannelView != null) {
            mFileChannelView.onActivityResult(requestCode, resultCode, data);
        }
    }

    /**
     * 播放成功回调
     *
     * @param roundId 当次游戏生命周期标识符
     * @param clarityId 当前游戏画面的清晰度，首帧渲染到画面时触发该回调
     */
    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        AcLog.d(TAG, "roundId " + roundId + " clarityId " + clarityId);
        VePhoneEngine.getInstance().getCameraManager().setRemoteRequestListener(new RemoteCameraRequestListener() {
            @Override
            public void onVideoStreamStartRequested(CameraId cameraId) {
                AcLog.d(TAG, "onVideoStreamStartRequested, cameraId :" + cameraId);
                VePhoneEngine.getInstance().getCameraManager().startVideoStream(cameraId);
            }

            @Override
            public void onVideoStreamStopRequested() {
                AcLog.d(TAG, "onVideoStreamStopRequested ");
                VePhoneEngine.getInstance().getCameraManager().stopVideoStream();
            }
        });
        VePhoneEngine.getInstance().getCameraManager().setCameraManagerListener(new CameraManagerListener() {
            @Override
            public void onLocalVideoStateChanged(LocalVideoStreamState localVideoStreamState, LocalVideoStreamError errorCode) {
                AcLog.d(TAG, "LocalVideoStreamState" + localVideoStreamState.toString() + ",LocalVideoStreamError" + errorCode);
            }

            @Override
            public void onFirstCapture() {
                AcLog.d(TAG, "onFirstCapture");
            }
        });

        vePhoneEngine.getClarityService().setStreamProfileChangeListener(new StreamProfileChangeCallBack() {
            @Override
            public void onVideoStreamProfileChange(boolean isSuccess, int from, int to) {
                AcLog.d(TAG, "VideoStreamProfileChange  isSuccess " + isSuccess + "from " + from + "to " + to);
            }

            @Override
            public void onError(int i, String s) {
                AcLog.d(TAG, "onError - " + s);
            }
        });

        vePhoneEngine.getClipBoardServiceManager().setBoardSyncClipListener(new IClipBoardListener() {
            @Override
            public void onClipBoardMessageReceived(ClipData clipData) {
                AcLog.d(TAG, "clipBoard : " + clipData.toString());
            }
        });
        tvInfo.setText(String.format(
                "podId: %s\nproductId: %s\nroundId: %s\nclarityId: %s\n",
                podId,
                productId,
                roundId,
                clarityId
        ));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            tvInfo.setZ(Long.MAX_VALUE);
        }
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        tvInfo = findViewById(R.id.tv_info);
    }

    /**
     * 初始化功能界面
     */
    private void initFeatures() {
        mContainers = findViewById(R.id.cl_container);
        btnAudio = findViewById(R.id.btn_audio);
        btnCamera = findViewById(R.id.btn_camera);
        btnClarity = findViewById(R.id.btn_clarity);
        btnClipBoard = findViewById(R.id.btn_clipboard);
        btnFileChannel = findViewById(R.id.btn_file_channel);
        btnFileExchange = findViewById(R.id.btn_file_exchange);
        btnGround = findViewById(R.id.btn_ground);
        btnLocation = findViewById(R.id.btn_location);
        btnMessageChannel = findViewById(R.id.btn_message_channel);
        btnPodControl = findViewById(R.id.btn_pod_control);
        btnPadConsole = findViewById(R.id.btn_pad_console);
        btnRotation = findViewById(R.id.btn_orientation);
        btnSensor = findViewById(R.id.btn_sensor);
        btnUnclassified = findViewById(R.id.btn_unclassified);
        btnLocalInput = findViewById(R.id.btn_local_input);

        findViewById(R.id.btn_show_info).setOnClickListener(v -> {
            isShowInfo = !isShowInfo;
            tvInfo.setVisibility(isShowInfo ? View.VISIBLE : View.GONE);
        });

        findViewById(R.id.btn_show_or_hide).setOnClickListener(v -> {
            mIsHideButtons = !mIsHideButtons;
            mContainers.setVisibility(mIsHideButtons ? View.GONE : View.VISIBLE);
        });

        if (vePhoneEngine.getClarityService() != null) {
            new ClarityServiceView(this, vePhoneEngine.getClarityService(), btnClarity);
        } else {
            AcLog.d(TAG, "ClarityService is null!");
        }

        btnRotation.setOnClickListener(view -> {
            if (isLand) {
                setRotation(270);
            } else {
                setRotation(0);
            }
            isLand = !isLand;
        });

        switch (getIntent().getIntExtra(KEY_FEATURE_ID, -1)) {
            case FEATURE_AUDIO: // 音频
                btnAudio.setVisibility(View.VISIBLE);
                btnAudio.setOnClickListener(view -> {
                    if (vePhoneEngine.getAudioService() != null) {
                        mDialogWrapper = DialogUtils.wrapper(
                                new AudioServiceView(this, vePhoneEngine.getAudioService()));
                        mDialogWrapper.show();
                    } else {
                        AcLog.d(TAG, "AudioService is null!");
                    }
                });
                break;
            case FEATURE_CAMERA: // 相机
                if (vePhoneEngine.getCameraManager() != null) {
                    new CameraManagerView(this, vePhoneEngine.getCameraManager(), btnCamera);
                } else {
                    AcLog.d(TAG, "CameraManager is null!");
                }
                break;
            case FEATURE_CLIPBOARD: // 剪切板
                if (vePhoneEngine.getClipBoardServiceManager() != null) {
                    new ClipBoardServiceManagerView(this, vePhoneEngine.getClipBoardServiceManager(), btnClipBoard);
                } else {
                    AcLog.d(TAG, "ClipBoardServiceManager is null!");
                }
                break;
            case FEATURE_FILE_CHANNEL: // 文件通道
                btnFileChannel.setVisibility(View.VISIBLE);
                btnFileChannel.setOnClickListener(view -> {
                    if (vePhoneEngine.getFileChannel() != null) {
                        mFileChannelView = new FileChannelView(this, vePhoneEngine.getFileChannel());
                        mDialogWrapper = DialogUtils.wrapper(mFileChannelView);
                        mDialogWrapper.show();
                    } else {
                        AcLog.d(TAG, "FileChannel is null!");
                    }
                });
                break;
            case FEATURE_FILE_EXCHANGE: // 大文件通道
                if (vePhoneEngine.getFileExchange() != null) {
                    new FileExchangeView(this, vePhoneEngine.getFileExchange(), btnFileExchange);
                }
                else {
                    AcLog.d(TAG, "FileChannelExt is null!");
                }
                break;
            case FEATURE_LOCAL_INPUT: // 本地输入
                if (vePhoneEngine.getLocalInputManager() != null) {
                    new LocalInputManagerView(this, vePhoneEngine.getLocalInputManager(), btnLocalInput);
                } else {
                    AcLog.d(TAG, "LocalInputManager is null!");
                }
                break;
            case FEATURE_LOCATION: // 定位服务
                if (vePhoneEngine.getLocationService() != null) {
                    new LocationServiceView(this, vePhoneEngine.getLocationService(), btnLocation);
                } else {
                    AcLog.d(TAG, "LocationService is null!");
                }
                break;
            case FEATURE_MESSAGE_CHANNEL: // 消息通道
                if (vePhoneEngine.getMessageChannel() != null) {
                    new MessageChannelView(this, vePhoneEngine.getMessageChannel(), btnMessageChannel);
                } else {
                    AcLog.d(TAG, "MessageChannel is null!");
                }
                break;
            case FEATURE_PAD_CONSOLE: // 游戏手柄
                if (vePhoneEngine.getGamePadService() != null) {
                    new PadConsoleManagerView(this, vePhoneEngine.getGamePadService(), btnPadConsole);
                } else {
                    AcLog.d(TAG, "GamePadService is null!");
                }
                break;
            case FEATURE_POD_CONTROL: // Pod控制
                if (vePhoneEngine.getPodControlService() != null) {
                    new PodControlServiceView(this, vePhoneEngine.getPodControlService(), btnPodControl);
                } else {
                    AcLog.d(TAG, "PodControlService is null!");
                }
                break;
            case FEATURE_SENSOR: // 传感器
                new SensorView(this, btnSensor);
                break;
            case FEATURE_UNCLASSIFIED: // 其他
                new UnclassifiedView(this, btnUnclassified);
                break;
            default:
                break;
        }
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


    /**
     * SDK内部产生的错误回调
     *
     * @param i 错误码
     * @param s 错误详情
     */
    @Override
    public void onError(int i, String s) {
        String msg = "onError:" + i + ", " + s;
        Toast.makeText(this, "code" + i + "msg" + s, Toast.LENGTH_SHORT).show();
        Log.e(TAG, msg);
    }

    /**
     * SDK内部产生的警告回调
     *
     * @param i 警告码
     * @param s 警告详情
     */
    @Override
    public void onWarning(int i, String s) {
        Log.d(TAG, "warn: code " + i + ", msg" + s);
    }

    /**
     * 网络连接类型和状态切换回调
     *
     * @param i 当前的网络类型
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
    public void onNetworkChanged(int i) {
        Log.d(TAG, String.format("%d", i));
    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit() {
        initFeatures();
    }

    /**
     * 收到音频首帧时的回调
     *
     * @param s 远端实例音频流的ID
     */
    @Override
    public void onFirstAudioFrame(String s) {
        Log.d(TAG, "onFirstAudioFrame " + s);
    }

    /**
     * 收到视频首帧时的回调
     *
     * @param s 远端实例视频流的ID
     */
    @Override
    public void onFirstRemoteVideoFrame(String s) {
        Log.d(TAG, "onFirstRemoteVideoFrame " + s);
    }

    /**
     * 开始播放的回调
     */
    @Override
    public void onStreamStarted() {
        Log.d(TAG, "onStreamStarted ");
    }

    /**
     * 暂停播放后的回调，调用pause()后会触发
     */
    @Override
    public void onStreamPaused() {
        Log.d(TAG, "onStreamPaused ");
    }

    /**
     * 恢复播放后的回调，调用resume()或muteAudio(false)后回触发
     */
    @Override
    public void onStreamResumed() {
        Log.d(TAG, "onStreamResumed ");
    }

    /**
     * 周期为2秒的音视频网络状态的回调，可用于内部数据分析或监控
     *
     * @param streamStats 远端视频流的性能状态
     */
    @Override
    public void onStreamStats(StreamStats streamStats) {
        Log.d(TAG, " " + streamStats.getDecoderOutputFrameRate() + " " +
                streamStats.getStallCount() + " " +
                streamStats.getReceivedResolutionHeight() + " " +
                streamStats.getReceivedResolutionWidth() + " " +
                streamStats.getRendererOutputFrameRate() + " " +
                streamStats.getDecoderOutputFrameRate() + " " +
                streamStats.getReceivedAudioBitRate() + " " +
                streamStats.getReceivedVideoBitRate());
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
        AcLog.d(TAG, "onNetworkQuality() called with: quality = [" + quality + "]");
    }

    /**
     * 周期为2秒的本地推送的音视频流的状态回调
     *
     * @param localStreamStats 本地音视频流的性能状态
     */
    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {
        AcLog.d(TAG, "LocalStreamStats" + localStreamStats);
    }

    /**
     * 视频流连接状态改变回调
     *
     * @param i 连接状态
     *          1 -- 连接断开
     *          2 -- 首次连接
     *          3 -- 首次连接成功
     *          4 -- 连接断开后重新连接中
     *          5 -- 连接断开后重新连接成功
     *          6 -- 连接断开超过10秒，仍然会继续重连
     */
    @Override
    public void onStreamConnectionStateChanged(int i) {
        Log.d(TAG, "onStreamConnectionStateChanged " + i);
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        AcLog.d(TAG, "onConfigurationChanged newConfig " + newConfig.orientation);
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    /**
     * 操作延迟回调
     *
     * @param l 操作延迟的具体值，单位:毫秒
     */
    @Override
    public void onDetectDelay(long l) {
        Log.d(TAG, "delay " + l);
    }


    /**
     * 客户端旋转回调
     *
     * @param i 旋转方向
     *          0, 180 -- 竖屏
     *         90, 270 -- 横屏
     */
    @Override
    public void onRotation(int i) {
        Log.d(TAG, "rotation" + i);
        setRotation(i);
    }

    /**
     * 远端实例退出回调
     *
     * @param i 退出的原因码
     * @param s 退出的原因详情
     */
    @Override
    public void onPodExit(int i, String s) {
        Log.d(TAG, "onPodExit" + i + " ,msg:" + s);
    }

    @Override
    public void onBackPressed() {
        long current = System.currentTimeMillis();
        if (current - lastBackPress < 1000L) {
            super.onBackPressed();
        } else {
            Toast.makeText(this, getString(R.string.back_again_to_exit), Toast.LENGTH_SHORT).show();
            lastBackPress = current;
        }
    }

    public static void startPhone(
            String podId,
            String productId,
            String roundId,
            int clarityId,
            Activity activity,
            int featureId) {
        Intent intent = new Intent(activity, PhoneActivity.class);
        intent.putExtra(PhoneActivity.KEY_POD_ID, podId);
        intent.putExtra(PhoneActivity.KEY_PRODUCT_ID, productId);
        if (roundId.isEmpty() || roundId.equals("")) {
            roundId = "123";
        }
        intent.putExtra(PhoneActivity.KEY_ROUND_ID, roundId);
        intent.putExtra(PhoneActivity.KEY_ClARITY_ID, clarityId);
        intent.putExtra(PhoneActivity.KEY_FEATURE_ID, featureId);
        activity.startActivity(intent);
    }
}
