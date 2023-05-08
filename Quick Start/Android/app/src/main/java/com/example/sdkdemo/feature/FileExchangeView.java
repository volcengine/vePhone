package com.example.sdkdemo.feature;

import android.app.Activity;
import android.content.Context;
import android.text.method.ScrollingMovementMethod;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ScrollView;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.FileExchange;

import java.io.File;

public class FileExchangeView {

    private static final String TAG = "FileExchangeView";
    private FileExchange mFileExchange;
    private Context mContext;
    private DialogUtils.DialogWrapper mDialogWrapper;
    private TestView mTestView;

    public FileExchangeView(Context context, FileExchange fileExchange, Button button) {
        this.mContext = context;
        this.mFileExchange = fileExchange;
        this.mTestView = new TestView(mContext);
        mDialogWrapper = DialogUtils.wrapper(mTestView);
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    public class TestView extends ScrollView implements View.OnClickListener {

        private Button mStartPushFileButton;
        private Button mStopPushFileButton;
        private Button mStartPullFileButton;
        private Button mStopPullFileButton;

        private EditText mFilePathEditText;
        private EditText mTargetPathEditText;
        private EditText mLogConsoleEditText;

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_file_exchange, this);
            setLayoutParams(new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            initView();
        }

        private void initView() {
            mStartPushFileButton = findViewById(R.id.btn_start_push_file);
            mStopPushFileButton = findViewById(R.id.btn_stop_push_file);
            mStartPullFileButton = findViewById(R.id.btn_start_pull_file);
            mStopPullFileButton = findViewById(R.id.btn_stop_pull_file);

            mStartPushFileButton.setOnClickListener(this);
            mStopPushFileButton.setOnClickListener(this);
            mStartPullFileButton.setOnClickListener(this);
            mStopPullFileButton.setOnClickListener(this);

            mFilePathEditText = findViewById(R.id.et_file_path);
            File file = new File("/sdcard/Download/", "1.mp4");
            mFilePathEditText.setText(file.getAbsolutePath());

            mTargetPathEditText = findViewById(R.id.et_target_path);
            File target = new File("/sdcard/Download");
            mTargetPathEditText.setText(target.getAbsolutePath());

            mLogConsoleEditText = findViewById(R.id.et_log_console);
            mLogConsoleEditText.setKeyListener(null);
            mLogConsoleEditText.setCursorVisible(false);
            mLogConsoleEditText.setFocusable(false);
            mLogConsoleEditText.setFocusableInTouchMode(false);
        }

        public void printLog(String log) {
            ((Activity) mContext).runOnUiThread(() -> {
                StringBuilder sb = new StringBuilder();
                sb.append(mLogConsoleEditText.getText().toString());
                sb.append("\r\n");
                sb.append(log);
                setText(sb.toString());
            });
        }

        @Override
        public void onClick(View view) {
            if (view.getId() == R.id.btn_start_push_file) {
                if (mFileExchange != null) {
                    File file = new File(mFilePathEditText.getText().toString());
                    File target = new File(mTargetPathEditText.getText().toString());
                    mFileExchange.startPushFile(file, target, mPushFileListener);
                }
            } else if (view.getId() == R.id.btn_stop_push_file) {
                if (mFileExchange != null) {
                    File file = new File(mFilePathEditText.getText().toString());
                    mFileExchange.stopPushFile(file);
                }
            } else if (view.getId() == R.id.btn_start_pull_file) {
                if (mFileExchange != null) {
                    File file = new File(mFilePathEditText.getText().toString());
                    mFileExchange.startPullFile(file, mPullFileListener);
                }
            } else if (view.getId() == R.id.btn_stop_pull_file) {
                File file = new File(mFilePathEditText.getText().toString());
                mFileExchange.stopPullFile(file);
            }
        }

        private void setText(String textString) {
            mLogConsoleEditText.setText(textString);
            mLogConsoleEditText.setMovementMethod(ScrollingMovementMethod.getInstance());
            mLogConsoleEditText.setSelection(mLogConsoleEditText.getText().length(), mLogConsoleEditText.getText().length());
        }

        private FileExchange.IPushFileListener mPushFileListener = new FileExchange.IPushFileListener() {
            @Override
            public void onStart(File file) {
                Log.d(TAG, "IPushFileListener.onStart() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPushFileListener.onStart() - " + file.getAbsolutePath());
                    setText(sb.toString());
                });
            }

            @Override
            public void onProgress(File file, int progress) {
                Log.d(TAG, "IPushFileListener.onProgress() - " + progress);
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPushFileListener.onProgress() - " + progress);
                    setText(sb.toString());
                });
            }

            @Override
            public void onComplete(File file) {
                Log.d(TAG, "IPushFileListener.onComplete() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPushFileListener.onComplete() - " + file.getAbsolutePath());
                    setText(sb.toString());
                });
            }

            @Override
            public void onCancel(File file) {
                Log.d(TAG, "IPushFileListener.onCancel() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPushFileListener.onCancel() - " + file.getAbsolutePath());
                    setText(sb.toString());
                });
            }

            @Override
            public void onError(File file, int err) {
                Log.d(TAG, "IPushFileListener.onError() - " + err);
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPushFileListener.onError() - " + err);
                    setText(sb.toString());
                });
            }
        };

        private FileExchange.IPullFileListener mPullFileListener = new FileExchange.IPullFileListener() {
            @Override
            public void onStart(File file) {
                Log.d(TAG, "IPullFileListener.onStart() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPullFileListener.onStart() - " + file.getAbsolutePath());
                    setText(sb.toString());
                });
            }

            @Override
            public void onProgress(File file, int progress) {
                Log.d(TAG, "IPullFileListener.onProgress() - " + progress);
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPullFileListener.onProgress() - " + progress);
                    setText(sb.toString());
                });
            }

            @Override
            public void onComplete(File file, String url) {
                Log.d(TAG, "IPullFileListener.onComplete() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPullFileListener.onComplete() - " + file.getAbsolutePath());
                    sb.append("IPullFileListener.onComplete() - " + url);
                    setText(sb.toString());
                });
            }

            @Override
            public void onCancel(File file) {
                Log.d(TAG, "ISendFileListener.onCancel() - " + file.getAbsolutePath());
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPullFileListener.onCancel() - " + file.getAbsolutePath());
                    setText(sb.toString());
                });
            }

            @Override
            public void onError(File file, int err) {
                Log.d(TAG, "IPullFileListener.onError() - " + err);
                ((Activity) mContext).runOnUiThread(() -> {
                    StringBuilder sb = new StringBuilder();
                    sb.append(mLogConsoleEditText.getText().toString());
                    sb.append("\r\n");
                    sb.append("IPullFileListener.onError() - " + err);
                    setText(sb.toString());
                });
            }
        };
    }
}
