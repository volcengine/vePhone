package com.example.sdkdemo.feature;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.text.method.ScrollingMovementMethod;
import android.view.View;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Toast;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.FileUtil;
import com.volcengine.cloudphone.apiservice.IFileChannel;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

public class FileChannelView extends ScrollView implements View.OnClickListener {

    private EditText mFilePathEditText, mLogcatEditText;
    private IFileChannel mFileChannelImpl;
    private File mFile;
    private Context mContext;
    private SeekBar mSeekBar;
    private final List<FileChannelView.LogcatInfo> mLogcatList = new ArrayList();
    private static final String TAG = "FileChannelView";

    public FileChannelView(Context context, IFileChannel iFileChannel) {
        super(context);
        this.mContext = context;
        this.mFileChannelImpl = iFileChannel;
        /**
         * setReceiveDataListener(IReceiveDataListener listener) -- 设置接收数据回调监听器
         */
        mFileChannelImpl.setReceiveDataListener(new IFileChannel.IReceiveDataListener() {
            @Override
            public void onDataReceived(byte[] payload) {
                addLog("duplex", "#Receive payload " + payload.length + " bytes size of data.");
            }
        });

        /**
         * setStatusListener(IChannelStatusListener listener) -- 设置文件传输通道内部状态回调监听器
         */
        mFileChannelImpl.setStatusListener(new IFileChannel.IChannelStatusListener() {
            @Override
            public void onStateUpdated(int status) {
                addLog("duplex", "#Status change to " + getStatusString(status) + ".");
            }
        });
        inflate(context, R.layout.dialog_file_channel, this);
        findViewById(R.id.btn_send_data).setOnClickListener(this);
        findViewById(R.id.btn_send_ack_data).setOnClickListener(this);
        findViewById(R.id.btn_get_status).setOnClickListener(this);
        findViewById(R.id.btn_choose_file).setOnClickListener(this);
        mSeekBar = findViewById(R.id.seekbar_timeout);
        mFilePathEditText = findViewById(R.id.et_file_path);
        mFilePathEditText.setText(mFile != null ? mFile.getAbsolutePath() : "");
        mFilePathEditText.setEnabled(false);
        mLogcatEditText = findViewById(R.id.et_logcat);
        mLogcatEditText.setCursorVisible(false);
        mLogcatEditText.setFocusable(false);
        mLogcatEditText.setFocusableInTouchMode(false);
        mLogcatEditText.setLongClickable(true);
        mLogcatEditText.setOnLongClickListener(new OnLongClickListener() {
            public boolean onLongClick(View view) {
                ClipboardManager clipboard = (ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
                ClipData clipData = ClipData.newPlainText((CharSequence)null, mLogcatEditText.getText());
                clipboard.setPrimaryClip(clipData);
                Toast.makeText(context, "Copy to Clipboard!", Toast.LENGTH_SHORT).show();
                return false;
            }
        });
    }

    private void updateLogcat() {
        ((Activity) mContext).runOnUiThread(() -> {
            StringBuilder sb = new StringBuilder();
            boolean first = true;

            for(int i = 0; i < mLogcatList.size(); ++i) {
                if (first) {
                    first = false;
                } else {
                    sb.append("\n");
                }

                sb.append((mLogcatList.get(i)).getMessage());
            }

            mLogcatEditText.setText(sb.toString());
            mLogcatEditText.setMovementMethod(ScrollingMovementMethod.getInstance());
            mLogcatEditText.setSelection(mLogcatEditText.getText().length(), mLogcatEditText.getText().length());
        });
    }

    private byte[] getPayload() throws Exception {
        byte[] data = null;

        try {
            if (mFile != null) {
                FileInputStream inputStream = new FileInputStream(mFile);
                byte[] bys = new byte[(int)mFile.length()];
                int offset = 0;

                int len;
                for(int remaining = (int)mFile.length(); (len = inputStream.read(bys, offset, Math.min(1024, remaining))) > 0; remaining -= len) {
                    offset += len;
                }

                data = bys;
            }

            return data;
        } catch (Exception exception) {
            throw exception;
        }
    }

    private void addLog(String tag, String message) {
        synchronized(this) {
            if (mLogcatList.size() > 2000) {
                mLogcatList.remove(0);
            }

            mLogcatList.add(new FileChannelView.LogcatInfo(tag, message, System.currentTimeMillis()));
            updateLogcat();
        }
    }

    private String getStatusString(int status) {
        switch(status) {
            case 1:
                return "IDLE";
            case 2:
                return "INITIALIZED";
            case 4:
                return "CONNECTING";
            case 8:
                return "CONNECTED";
            case 16:
                return "DISCONNECTED";
            default:
                return "UNKNOWN";
        }
    }

    public void setFile(File file) {
        this.mFile = file;
        this.mFilePathEditText.setText(this.mFile != null ? this.mFile.getAbsolutePath() : "");
    }

    @Override
    public void onClick(View view) {
        byte[] payload;
        if (view.getId() == R.id.btn_send_data) {
            try {
                if (mFile != null && mFile.exists()) {
                    payload = getPayload();
                    /**
                     * sendData(byte[] payload) -- 发送数据包到云端游戏，无数据发送到达回执
                     *
                     * @param payload 发送的数据包(支持发送的数据包不大于5MB，
                     *                如果发送的数据大于5MB，将抛出 IllegalArgumentException 异常)
                     */
                    mFileChannelImpl.sendData(payload);
                } else {
                    addLog("duplex", "#The file does not exist.");
                }
            } catch (Exception e) {
                addLog("duplex", "#" + e.getMessage());
            }
        } else if (view.getId() == R.id.btn_send_ack_data) {
            try {
                if (mFile != null && mFile.exists()) {
                    payload = getPayload();
                    int timeout = mSeekBar.getProgress() * 1000;
                    /**
                     * sendData(byte[] payload, long timeout, ISendDataListener listener) -- 发送数据包到云端游戏，有数据发送到达回执
                     *
                     * @param payload 发送的数据包
                     * @param timeout 接收回执超时时长，单位毫秒
                     * @param listener 用于接收数据发送到达回执
                     */
                    mFileChannelImpl.sendData(payload, (long)timeout, new IFileChannel.ISendDataListener() {
                        public void onDataSend() {
                            addLog("duplex", "#Send payload and receive ACK success!!!");
                        }

                        public void onError(int err) {
                            addLog("duplex", "#Send payload failed - " + err);
                        }
                    });
                } else {
                    addLog("duplex", "#The file does not exist.");
                }
            } catch (Exception e) {
                addLog("duplex", "#" + e.getMessage());
            }
        } else if (view.getId() == R.id.btn_get_status) {
            /**
             * getStatus() -- 获取当前FileChannelEngine的内部状态
             */
            addLog("duplex", "#Status is " + getStatusString(mFileChannelImpl.getStatus()) + ".");
        } else if (view.getId() == R.id.btn_choose_file) {
            Intent intent = new Intent("android.intent.action.GET_CONTENT");
            intent.setType("*/*");
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            ((Activity) mContext).startActivityForResult(Intent.createChooser(intent, "请选择文件"), 1);
        }
    }

    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == 1 && resultCode == Activity.RESULT_OK) {
            Uri uri = data.getData();
            if (uri != null) {
                try {
                    File file = FileUtil.from(mContext, uri);
                    if (file != null && file.exists()) {
                        setFile(file);
                    }
                } catch (IOException e) {
                    e.printStackTrace();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    }

    private static class LogcatInfo {
        private final String tag;
        private final String message;
        private final long timestamp;

        public LogcatInfo(String tag, String message, long timestamp) {
            this.tag = tag;
            this.message = message;
            this.timestamp = timestamp;
        }

        public String getMessage() {
            return this.message;
        }

        public String getTimestamp() {
            Date date = new Date(this.timestamp);
            SimpleDateFormat sd = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            return sd.format(date);
        }

        public String toString() {
            return this.getMessage();
        }
    }

}
