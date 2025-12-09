package com.example.sdkdemo.feature;

import android.content.ClipData;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.IClipBoardListener;
import com.volcengine.cloudphone.apiservice.IClipBoardServiceManager;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.Map;


/**
 * 该类用于展示与剪切板{@link IClipBoardServiceManager}相关的功能接口
 * 使用该服务可以实现向云端实例发送剪切板数据的功能。
 */
public class ClipBoardServiceManagerActivity extends BasePlayActivity {

    private FrameLayout mContainer;
    private IClipBoardServiceManager mClipBoardServiceManager;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnSend;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_clipboard);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnSend = findViewById(R.id.btn_send);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnSend.setOnClickListener(view -> {
            if (mClipBoardServiceManager != null) {
                /**
                 * sendClipBoardMessage(ClipData clipData) -- 发送本地剪切板消息到云端实例
                 *
                 * @param clipData 剪切板数据
                 */
                mClipBoardServiceManager.sendClipBoardMessage(
                        ClipData.newPlainText("test", "test data"));
            }
            else {
                Log.e(TAG, "mClipBoardServiceManager == null");
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
        mClipBoardServiceManager = VePhoneEngine.getInstance().getClipBoardServiceManager();
        if (mClipBoardServiceManager != null) {
            /*
             * setBoardSyncClipListener(IClipBoardListener listener) -- 设置云端同步剪切板数据的监听器
             */
            mClipBoardServiceManager.setBoardSyncClipListener(new IClipBoardListener() {
                /**
                 * 云端收到本地发送的剪切板数据后的回调
                 *
                 * @param clipData 云端同步到本地的剪切板数据
                 */
                @Override
                public void onClipBoardMessageReceived(ClipData clipData) {
                    Log.i(TAG, "[onClipBoardMessageReceived] clipData: " + clipData.getItemAt(0).getText());
                    showToast("[onClipBoardMessageReceived] clipData: " + clipData.getItemAt(0).getText());
                }
            });
        }
        else {
            Log.e(TAG, "mClipBoardServiceManager == null");
        }
    }

}
