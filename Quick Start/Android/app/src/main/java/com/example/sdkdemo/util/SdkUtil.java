package com.example.sdkdemo.util;


import android.content.Context;
import android.text.TextUtils;

import androidx.annotation.NonNull;

import com.volcengine.common.SDKContext;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONObject;

public class SdkUtil {


    /**
     * 需在manifest文件中配置accountId
     */
    public static boolean checkHasConfigAccountIdInManifest() {
        return !TextUtils.isEmpty(SDKContext.getAccountId());
    }


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
    public static @NonNull PlayAuth getPlayAuth(Context context) {
        PlayAuth auth = new PlayAuth();
        try {
            JSONObject stsJObj = new JSONObject(AssetsUtil.getTextFromAssets(context, "sts.json"));
            return new PlayAuth(
                    stsJObj.getString("ak"),
                    stsJObj.getString("sk"),
                    stsJObj.getString("token"),
                    stsJObj.getString("productId"),
                    stsJObj.getString("podId")
            );
        } catch (Throwable ignore) {
        }
        return auth;
    }


    /**
     * 生成客户端用户id
     * 推荐采用：`{OS}_{DEVICE_ID}`的格式用于区分不同系统和设备，防止出现预期外的userId重复
     */
    public @NonNull static String getClientUid() {
        return "android_github_" + VePhoneEngine.getInstance().getDeviceId();
    }

    public static class PlayAuth {
        public String ak, sk, token, productId, podId;

        public PlayAuth() {
        }

        public PlayAuth(String ak, String sk, String token, String productId, String podId) {
            this.ak = ak;
            this.sk = sk;
            this.token = token;
            this.productId = productId;
            this.podId = podId;
        }
    }
}
