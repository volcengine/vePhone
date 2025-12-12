package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.StreamProfileChangeCallBack;
import com.volcengine.cloudphone.apiservice.StreamProfileManager;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与清晰度{@link StreamProfileManager}相关的功能接口
 * 可以通过该服务实现设置云端实例推流清晰度档位的功能。
 */
public class ClarityServiceActivity extends BasePlayActivity {

    private FrameLayout mContainer;
    private StreamProfileManager mClarityService;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnSend, mBtnGet;
    EditText mEtClarityId;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_clarity);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mEtClarityId = findViewById(R.id.et_clarity_id);
        mBtnSend = findViewById(R.id.btn_send);
        mBtnGet = findViewById(R.id.btn_get_profile);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnSend.setOnClickListener(view -> {
            int clarityId = Integer.parseInt(mEtClarityId.getText().toString());
            if (mClarityService != null) {
                mClarityService.switchVideoStreamProfileId(clarityId);
            }
            else {
                Log.e(TAG, "mClarityService == null");
            }
        });

        mBtnGet.setOnClickListener(view -> {
            if (mClarityService != null) {
                Toast.makeText(this, mClarityService.getCurrentVideoStreamProfile().toString(), Toast.LENGTH_SHORT).show();
            }
            else {
                Log.e(TAG, "mClarityService == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(SdkUtil.getClientUid())
                            .ak(auth.ak)
                            .sk(auth.sk)
                            .token(auth.token)
                            .container(mContainer)
                            .enableLocalKeyboard(true)
                            .roundId(SdkUtil.getRoundId())
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .streamListener(this);
                    VePhoneEngine.getInstance().start(builder.build(), this);
                },
                p -> {
                    showTipDialog(MessageFormat.format(getString(R.string.invalid_phone_play_config) , p));
                });
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
        mClarityService = VePhoneEngine.getInstance().getClarityService();
        if (mClarityService != null) {
            mClarityService.setStreamProfileChangeListener(new StreamProfileChangeCallBack() {
                @Override
                public void onVideoStreamProfileChange(boolean success, int from, int to) {
                    Log.i(TAG, "[onVideoStreamProfileChange] success: " + success + ", from: " + from + ", to: " + to);
                    Toast.makeText(ClarityServiceActivity.this, "success: " + success + ", from: " + from + ", to: " + to, Toast.LENGTH_SHORT).show();
                }

                @Override
                public void onError(int errorCode, String errorMessage) {
                    Log.i(TAG, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage);
                }
            });
        }
        else {
            Log.e(TAG, "mClarityService == null");
        }
    }
}
