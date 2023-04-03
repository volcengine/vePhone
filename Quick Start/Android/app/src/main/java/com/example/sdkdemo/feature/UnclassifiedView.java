package com.example.sdkdemo.feature;

import android.app.Activity;
import android.content.Context;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.phone.VePhoneEngine;

public class UnclassifiedView {

    private final DialogUtils.DialogWrapper mDialogWrapper;


    public UnclassifiedView(Context context, Button button) {
        mDialogWrapper = DialogUtils.wrapper(new TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private static class TestView extends LinearLayout {

        private final Activity mActivity;

        public TestView(Context context) {
            super(context);
            mActivity = (Activity) context;
            inflate(context, R.layout.dialog_unclassified, this);

            findViewById(R.id.btn_throw_exception).setOnClickListener(v -> {
                throw new IllegalArgumentException("test");
            });

            /**
             * restart() -- 重启服务端游戏进程
             */
            findViewById(R.id.btn_restart).setOnClickListener(v -> {
//                VePhoneEngine.getInstance().restart();
            });

            findViewById(R.id.btn_stop).setOnClickListener(v -> {
                if (mActivity != null) {
                    mActivity.finish();
                }
            });

            /**
             * pause() -- 暂停从云端拉流
             */
            findViewById(R.id.btn_pause).setOnClickListener(v -> {
                VePhoneEngine.getInstance().pause();
            });

            /**
             * resume() -- 恢复从云端拉流
             */
            findViewById(R.id.btn_resume).setOnClickListener(v -> {
                VePhoneEngine.getInstance().resume();
            });
        }

    }
}
