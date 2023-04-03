package com.example.sdkdemo.feature;

import android.content.ClipData;
import android.content.Context;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.IClipBoardServiceManager;

public class ClipBoardServiceManagerView {

    private IClipBoardServiceManager mClipBoardServiceManager;
    private DialogUtils.DialogWrapper mDialogWrapper;

    public ClipBoardServiceManagerView(Context context, IClipBoardServiceManager clipBoardServiceManager, Button button) {
        this.mClipBoardServiceManager = clipBoardServiceManager;
        mDialogWrapper = DialogUtils.wrapper(new TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends LinearLayout {

        public TestView(Context context) {
            super(context);
            setOrientation(VERTICAL);
            inflate(context, R.layout.dialog_clipboard, this);

            /**
             * sendClipBoardMessage(ClipData data) -- 发送本地剪切板消息到云端实例
             *
             * @param data 剪切板数据
             */
            findViewById(R.id.btn_send_clipData).setOnClickListener(v -> {
                mClipBoardServiceManager.sendClipBoardMessage(ClipData.newPlainText("test", "test data"));
            });
        }
    }
}
