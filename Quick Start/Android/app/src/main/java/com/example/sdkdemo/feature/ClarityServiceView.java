package com.example.sdkdemo.feature;

import android.content.Context;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.StreamProfileManager;

import java.util.Arrays;
import java.util.List;

public class ClarityServiceView {

    private Button btnClarity0, btnClarity1, btnClarity2, btnClarity3, btnClarity4, btnClarity5;
    private StreamProfileManager mClarityService;
    private DialogUtils.DialogWrapper mDialogWrapper;

    public ClarityServiceView(Context context, StreamProfileManager clarityService, Button button) {
        this.mClarityService = clarityService;
        mDialogWrapper = DialogUtils.wrapper(new TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends LinearLayout {
        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_clarity, this);
            setOrientation(VERTICAL);
            btnClarity0 = findViewById(R.id.btn_clarity_0);
            btnClarity1 = findViewById(R.id.btn_clarity_1);
            btnClarity2 = findViewById(R.id.btn_clarity_2);
            btnClarity3 = findViewById(R.id.btn_clarity_3);
            btnClarity4 = findViewById(R.id.btn_clarity_4);
            btnClarity5 = findViewById(R.id.btn_clarity_5);
            /**
             * switchVideoStreamProfileId(int streamProfileId) -- 切换视频流的清晰度
             *
             * @param streamProfileId 清晰度ID
             */
            findViewById(R.id.btn_send).setOnClickListener(v -> {
                EditText editText = findViewById(R.id.et_clarity_id);
                int clarityId = Integer.parseInt(editText.getText().toString());
                mClarityService.switchVideoStreamProfileId(clarityId);
            });
            initClarity();
        }


        private void initClarity() {
            List<Button> list = Arrays.asList(btnClarity0, btnClarity1, btnClarity2, btnClarity3, btnClarity4, btnClarity5);
            for (int i = 0; i < list.size(); i++) {
                Button button = list.get(i);
                int id = i;
                button.setOnClickListener(v -> mClarityService.switchVideoStreamProfileId(id));
            }
            btnClarity4.setOnClickListener(new OnClickListener() {
                @Override
                public void onClick(View v) {
                    mClarityService.switchVideoStreamProfileId(6);

                }
            });
            btnClarity5.setOnClickListener(new OnClickListener() {
                @Override
                public void onClick(View v) {
                    mClarityService.switchVideoStreamProfileId(16);
                }
            });
        }
    }
}
