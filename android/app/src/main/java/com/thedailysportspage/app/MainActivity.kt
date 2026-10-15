package com.thedailysportspage.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.setPadding
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams

class MainActivity : AppCompatActivity(), PurchasesUpdatedListener {
    private lateinit var billingClient: BillingClient
    private var productDetails: ProductDetails? = null
    private lateinit var root: LinearLayout
    private val paper = Color.rgb(245, 240, 228)
    private val ink = Color.rgb(17, 17, 17)
    private val red = Color.rgb(139, 30, 45)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        billingClient = BillingClient.newBuilder(this)
            .setListener(this)
            .enablePendingPurchases(
                PendingPurchasesParams.newBuilder().enableOneTimeProducts().build()
            )
            .enableAutoServiceReconnection()
            .build()
        showLoading("Checking subscription…")
        connectBilling()
    }

    override fun onResume() {
        super.onResume()
        if (::billingClient.isInitialized && billingClient.isReady) refreshPurchases()
    }

    override fun onDestroy() {
        if (::billingClient.isInitialized) billingClient.endConnection()
        super.onDestroy()
    }

    private fun connectBilling() {
        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    queryProduct()
                    refreshPurchases()
                } else {
                    showPaywall("Google Play subscriptions are temporarily unavailable.")
                }
            }

            override fun onBillingServiceDisconnected() = Unit
        })
    }

    private fun queryProduct() {
        val product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(MONTHLY_PRODUCT_ID)
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        val params = QueryProductDetailsParams.newBuilder().setProductList(listOf(product)).build()
        billingClient.queryProductDetailsAsync(params) { result, detailsResult ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                productDetails = detailsResult.productDetailsList.firstOrNull()
                if (productDetails == null) showPaywall("The subscription is not available yet.")
            }
        }
    }

    private fun refreshPurchases() {
        val params = QueryPurchasesParams.newBuilder()
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        billingClient.queryPurchasesAsync(params) { result, purchases ->
            if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                showPaywall("Unable to confirm your subscription. Please try again.")
                return@queryPurchasesAsync
            }
            val active = purchases.firstOrNull {
                it.products.contains(MONTHLY_PRODUCT_ID) &&
                    it.purchaseState == Purchase.PurchaseState.PURCHASED
            }
            if (active != null) {
                acknowledge(active)
                showEdition(active.purchaseToken)
            } else {
                showPaywall(null)
            }
        }
    }

    private fun acknowledge(purchase: Purchase) {
        if (purchase.isAcknowledged) return
        val params = AcknowledgePurchaseParams.newBuilder()
            .setPurchaseToken(purchase.purchaseToken)
            .build()
        billingClient.acknowledgePurchase(params) { }
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) {
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> purchases?.forEach {
                if (it.purchaseState == Purchase.PurchaseState.PURCHASED) {
                    acknowledge(it)
                    showEdition(it.purchaseToken)
                }
            }
            BillingClient.BillingResponseCode.USER_CANCELED -> Unit
            else -> showPaywall("The purchase could not be completed. Please try again.")
        }
    }

    private fun purchase() {
        val details = productDetails ?: run {
            queryProduct()
            showPaywall("The subscription is still loading. Please try again.")
            return
        }
        val offerToken = details.subscriptionOfferDetails
            ?.firstOrNull()
            ?.offerToken
            ?: run {
                showPaywall("The monthly subscription is not configured in Google Play yet.")
                return
            }
        val productParams = BillingFlowParams.ProductDetailsParams.newBuilder()
            .setProductDetails(details)
            .setOfferToken(offerToken)
            .build()
        val flowParams = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(listOf(productParams))
            .build()
        billingClient.launchBillingFlow(this, flowParams)
    }

    private fun showLoading(message: String) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            runOnUiThread { showLoading(message) }
            return
        }
        root = verticalLayout().apply {
            gravity = Gravity.CENTER
            addView(ProgressBar(this@MainActivity))
            addView(text(message, 17f).apply { gravity = Gravity.CENTER })
        }
        setContentView(root)
    }

    private fun showPaywall(error: String?) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            runOnUiThread { showPaywall(error) }
            return
        }
        val content = verticalLayout().apply {
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24))
            addView(text("The Daily Sports Page", 39f, Typeface.BOLD).apply {
                gravity = Gravity.CENTER
                setTextColor(ink)
            })
            addView(rule(3, ink))
            addView(text("THE SPORTS SECTION, REIMAGINED", 12f, Typeface.BOLD).apply {
                gravity = Gravity.CENTER
                letterSpacing = .12f
            })
            addView(text("Your front-row seat, every day.", 28f, Typeface.BOLD).apply {
                setPadding(0, dp(30), 0, dp(12))
            })
            addView(text("Original stories and the complete sports page—built for fans who still love box scores with their morning coffee.", 17f))
            addView(text("✓ Daily baseball and weekly football editions\n✓ Original headlines and game stories\n✓ Box scores, standings, schedules, and league leaders\n✓ Major-market editions and offline reading", 16f).apply {
                setLineSpacing(dp(5).toFloat(), 1f)
                setPadding(0, dp(22), 0, dp(22))
            })

            val price = productDetails?.subscriptionOfferDetails
                ?.firstOrNull()?.pricingPhases?.pricingPhaseList?.lastOrNull()?.formattedPrice
                ?: "$2.99"
            addView(text("7 days free, then $price per month", 18f, Typeface.BOLD).apply {
                gravity = Gravity.CENTER
            })
            addView(Button(this@MainActivity).apply {
                text = "Start 7-Day Free Trial"
                setTextColor(Color.WHITE)
                setBackgroundColor(ink)
                setOnClickListener { purchase() }
            }, matchWidth(dp(52), dp(12)))
            addView(Button(this@MainActivity).apply {
                text = "Restore Purchase"
                setOnClickListener { refreshPurchases() }
            }, matchWidth(dp(48), dp(6)))
            error?.let {
                addView(text(it, 14f).apply {
                    gravity = Gravity.CENTER
                    setTextColor(red)
                    setPadding(0, dp(12), 0, 0)
                })
            }
            addView(text("Subscription renews automatically unless canceled. Manage or cancel it in your Google Play account.", 12f).apply {
                gravity = Gravity.CENTER
                setPadding(0, dp(22), 0, dp(12))
            })
            addView(Button(this@MainActivity).apply {
                text = "Privacy Policy"
                setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(PRIVACY_URL))) }
            })
        }
        setContentView(ScrollView(this).apply {
            setBackgroundColor(paper)
            addView(content)
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun showEdition(purchaseToken: String) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            runOnUiThread { showEdition(purchaseToken) }
            return
        }
        setContentView(WebView(this).apply {
            setBackgroundColor(paper)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.loadWithOverviewMode = true
            settings.useWideViewPort = true
            webViewClient = object : WebViewClient() {
                private var authorized = false

                override fun onPageFinished(view: WebView, url: String) {
                    if (!authorized && Uri.parse(url).path == Uri.parse(ACCESS_URL).path) {
                        authorized = true
                        view.loadUrl(EDITION_URL)
                    }
                }

                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val uri = request.url
                    return if (uri.host == "thedailysportspage.com" || uri.host == "www.thedailysportspage.com") {
                        false
                    } else {
                        true
                    }
                }
            }
            val escapedToken = purchaseToken
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
            postUrl(
                ACCESS_URL,
                "{\"purchaseToken\":\"$escapedToken\"}".toByteArray(Charsets.UTF_8),
            )
        })
    }

    private fun verticalLayout() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(paper)
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.MATCH_PARENT,
        )
    }

    private fun text(value: String, size: Float, style: Int = Typeface.NORMAL) = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(ink)
        setTypeface(Typeface.SERIF, style)
    }

    private fun rule(height: Int, color: Int) = View(this).apply {
        setBackgroundColor(color)
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(height)).apply {
            topMargin = dp(6)
            bottomMargin = dp(6)
        }
    }

    private fun matchWidth(height: Int, marginTop: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        height,
    ).apply { topMargin = marginTop }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    companion object {
        const val MONTHLY_PRODUCT_ID = "com.thedailysportspage.app.monthly"
        const val EDITION_URL = "https://thedailysportspage.com/subscriber/current/"
        const val ACCESS_URL = "https://thedailysportspage.com/api/access/google"
        const val PRIVACY_URL = "https://thedailysportspage.com/privacy/"
    }
}
