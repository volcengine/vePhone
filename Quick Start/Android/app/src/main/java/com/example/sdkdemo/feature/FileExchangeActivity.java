package com.example.sdkdemo.feature;

import android.Manifest;
import android.os.Bundle;
import android.os.Environment;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.FileExchange;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.io.File;
import java.util.Map;

/**
 * 该类用于展示与大文件通道{@link FileExchange}相关的功能接口
 * 使用该服务可以实现向云端实例发送本地文件、上传云端实例的文件到云存储的功能。
 */
public class FileExchangeActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private FileExchange mFileExchange;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnStartPushFile, mBtnStopPushFile, mBtnStartPullFile, mBtnStopPullFile;
    private File mPushFile = new File(Environment.getExternalStorageDirectory().getPath(), "Download/test.apk");

    /**
     * 对于云端实例，不要使用下面这种写法定义文件，否则会推送(拉取)文件失败；
     * private File mTargetDirectory = new File(Environment.getExternalStorageDirectory().getPath(), "Download");
     * private File mPullFile = new File(Environment.getExternalStorageDirectory().getPath(), "Download/test.apk");
     */
    private File mTargetDirectory = new File("/sdcard/Download"); // 这里需要定义一个目录(文件夹)，推送的文件会存储到该目录下。
    private File mPullFile = new File("/sdcard/Download/douyin.apk");

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_file_exchange);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnStartPushFile = findViewById(R.id.btn_start_push_file);
        mBtnStopPushFile = findViewById(R.id.btn_stop_push_file);
        mBtnStartPullFile = findViewById(R.id.btn_start_pull_file);
        mBtnStopPullFile = findViewById(R.id.btn_stop_pull_file);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnStartPushFile.setOnClickListener(v -> {
            if (mFileExchange != null) {
                requestPermissionAndStartPushFile();
            }
            else {
                Log.e(TAG, "mFileExchange == null");
            }
        });

        mBtnStopPushFile.setOnClickListener(v -> {
            if (mFileExchange != null) {
                /**
                 * 停止向云端实例推送文件
                 * stopPushFile(File file)
                 *
                 * @param file 推送的本地文件
                 */
                mFileExchange.stopPushFile(mPushFile);
            }
            else {
                Log.e(TAG, "mFileExchange == null");
            }
        });

        mBtnStartPullFile.setOnClickListener(v -> {
            if (mFileExchange != null) {
                /**
                 * 拉取云端实例中的文件到云存储并返回http下载地址
                 * startPullFile(File file, IPullFileListener listener)
                 *
                 * @param file 拉取的云端实例文件
                 * @param listener 拉取文件的监听器，用于接收拉取进度和到达回执
                 */
                mFileExchange.startPullFile(mPullFile, new FileExchange.IPullFileListener() {
                    /**
                     * 拉取开始的回调
                     *
                     * @param file 拉取的云端实例文件
                     */
                    @Override
                    public void onStart(File file) {
                        Log.i(TAG, "IPullFileListener.onStart() - " + file.getAbsolutePath());
                    }

                    /**
                     * 拉取进度变化时的回调
                     *
                     * @param file 拉取的云端实例文件
                     * @param progress 拉取进度，取值范围[0, 100]
                     */
                    @Override
                    public void onProgress(File file, int progress) {
                        Log.i(TAG, "IPullFileListener.onProgress() - " + file.getAbsolutePath() + ", progress: " + progress);
                    }

                    /**
                     * 拉取完成时的回调
                     *
                     * @param file 拉取的云端实例文件
                     * @param url 文件下载地址
                     */
                    @Override
                    public void onComplete(File file, String url) {
                        Log.i(TAG, "IPullFileListener.onComplete() - " + file.getAbsolutePath() + ", url: " + url);
                    }

                    /**
                     * 拉取取消时的回调
                     *
                     * @param file 拉取的云端实例文件
                     */
                    @Override
                    public void onCancel(File file) {
                        Log.i(TAG, "IPullFileListener.onCancel() - " + file.getAbsolutePath());
                    }

                    /**
                     * 拉取失败时的回调
                     *
                     * @param file 拉取的云端实例文件
                     * @param errorCode 拉取失败的错误码
                     */
                    @Override
                    public void onError(File file, int errorCode) {
                        Log.i(TAG, "IPullFileListener.onError() - " + file.getAbsolutePath() + ", errorCode: " + errorCode);
                    }
                });
            }
            else {
                Log.e(TAG, "mFileExchange == null");
            }
        });

        mBtnStopPullFile.setOnClickListener(v -> {
            if (mFileExchange != null) {
                /**
                 * 停止拉取云端实例文件到云存储
                 * stopPullFile(File file)
                 *
                 * @param file 拉取的云端实例文件
                 */
                mFileExchange.stopPullFile(mPullFile);
            }
            else {
                Log.e(TAG, "mFileExchange == null");
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
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mFileExchange = VePhoneEngine.getInstance().getFileExchange();
    }

    private void requestPermissionAndStartPushFile() {
        PermissionUtils.permission(Manifest.permission.READ_EXTERNAL_STORAGE)
                .callback(new PermissionUtils.SimpleCallback() {
                    @Override
                    public void onGranted() {
                        /**
                         * 推送本地文件到云端实例的指定目录
                         * startPushFile(File file, File target, IPushFileListener listener)
                         *
                         * @param file 推送的本地文件
                         * @param target 云端实例的指定目录
                         * @param listener 推送文件的监听器，用于接收推送进度和到达回执
                         */
                        mFileExchange.startPushFile(mPushFile, mTargetDirectory, new FileExchange.IPushFileListener() {
                            /**
                             * 推送开始的回调
                             *
                             * @param file 推送的本地文件
                             */
                            @Override
                            public void onStart(File file) {
                                Log.d(TAG, "IPushFileListener.onStart() - " + file.getAbsolutePath());
                            }

                            /**
                             * 推送进度变化时的回调
                             *
                             * @param file 推送的本地文件
                             * @param progress 推送进度，取值范围[0, 100]
                             */
                            @Override
                            public void onProgress(File file, int progress) {
                                Log.d(TAG, "IPushFileListener.onProgress() - " + file.getAbsolutePath() + ", progress: " + progress);
                            }

                            /**
                             * 推送完成时的回调
                             *
                             * @param file 推送的本地文件
                             */
                            @Override
                            public void onComplete(File file) {
                                Log.d(TAG, "IPushFileListener.onComplete() - " + file.getAbsolutePath());
                            }

                            /**
                             * 推送取消时的回调
                             *
                             * @param file 推送的本地文件
                             */
                            @Override
                            public void onCancel(File file) {
                                Log.d(TAG, "IPushFileListener.onCancel() - " + file.getAbsolutePath());
                            }

                            /**
                             * 推送失败时的回调
                             *
                             * @param file 推送的本地文件
                             * @param errorCode 推送失败的错误码
                             */
                            @Override
                            public void onError(File file, int errorCode) {
                                Log.d(TAG, "IPushFileListener.onError() - " + file.getAbsolutePath() + ", errorCode: " + errorCode);
                            }
                        });
                    }

                    @Override
                    public void onDenied() {
                        showToast("无读取文件权限");
                    }
                })
                .request();
    }
}
