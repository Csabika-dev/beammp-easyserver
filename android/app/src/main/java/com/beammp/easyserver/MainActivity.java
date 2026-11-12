package com.beammp.easyserver;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.net.http.SslCertificate;
import android.net.http.SslError;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.Locale;

/**
 * BeamMP EasyServer phone app: the dashboard in a full-screen WebView.
 *
 * The dashboard uses its own (self-made) HTTPS certificate. Instead of trusting
 * any certificate, the app remembers the certificate's SHA-256 fingerprint from
 * the QR code shown in the dashboard (Settings -> Phone app) and only connects
 * when the server shows exactly that certificate.
 */
public class MainActivity extends Activity {
    private static final int PICK_FILE = 1;
    private SharedPreferences prefs;
    private WebView web;
    private ValueCallback<Uri[]> fileCallback;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("server", MODE_PRIVATE);
        boolean fromLink = readLink(getIntent());
        if (prefs.getString("url", "").isEmpty()) {
            showSetup(null);
        } else {
            showDashboard();
            if (fromLink) toast("Connected to " + prefs.getString("url", ""));
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (readLink(intent)) {
            showDashboard();
            toast("Connected to " + prefs.getString("url", ""));
        }
    }

    /** easyserver://connect?url=https://192.168.1.20:30815/&fp=<sha256 hex> */
    private boolean readLink(Intent intent) {
        Uri data = intent == null ? null : intent.getData();
        if (data == null || !"easyserver".equals(data.getScheme()) || !"connect".equals(data.getHost())) return false;
        String url = data.getQueryParameter("url");
        String fp = data.getQueryParameter("fp");
        if (!validUrl(url)) {
            toast("That QR code doesn't contain a dashboard address");
            return false;
        }
        save(url, fp);
        return true;
    }

    private static boolean validUrl(String url) {
        if (url == null) return false;
        Uri u = Uri.parse(url.trim());
        return "https".equals(u.getScheme()) && u.getHost() != null && !u.getHost().isEmpty();
    }

    private void save(String url, String fp) {
        url = url.trim();
        if (!url.endsWith("/")) url = url + "/";
        String clean = fp == null ? "" : fp.replaceAll("[^0-9a-fA-F]", "").toLowerCase(Locale.ROOT);
        prefs.edit().putString("url", url).putString("fp", clean).apply();
    }

    // ------------------------------------------------------------------ setup screen
    private void showSetup(String problem) {
        if (web != null) {
            web.destroy();
            web = null;
        }
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(22);
        box.setPadding(pad, dp(48), pad, pad);
        box.setBackgroundColor(Color.rgb(21, 21, 20));

        TextView title = text("BeamMP Dashboard", 24, true);
        box.addView(title);
        if (problem != null) {
            TextView p = text(problem, 15, false);
            p.setTextColor(Color.rgb(255, 140, 120));
            p.setPadding(0, dp(12), 0, 0);
            box.addView(p);
        }
        box.addView(text("\nEasiest: on your computer open the dashboard → Settings → Phone app, and scan the QR code "
                + "with this phone's camera. The app connects by itself.\n\nOr type the address yourself:", 15, false));

        EditText url = new EditText(this);
        url.setHint("https://192.168.1.20:30815");
        url.setText(prefs.getString("url", ""));
        url.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        url.setSingleLine(true);
        url.setTextColor(Color.WHITE);
        url.setHintTextColor(Color.GRAY);
        box.addView(url);

        box.addView(text("\nCertificate fingerprint (SHA-256) - shown in Settings → Access from the internet. "
                + "Needed because the dashboard makes its own certificate:", 13, false));
        EditText fp = new EditText(this);
        fp.setHint("AB:CD:EF:…");
        fp.setText(prefs.getString("fp", ""));
        fp.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        fp.setTextColor(Color.WHITE);
        fp.setHintTextColor(Color.GRAY);
        box.addView(fp);

        Button go = new Button(this);
        go.setText("Connect");
        go.setOnClickListener(v -> {
            String u = url.getText().toString().trim();
            if (!u.startsWith("https://")) u = "https://" + u.replaceFirst("^https?://", "");
            if (!validUrl(u)) {
                toast("Type the address like https://192.168.1.20:30815");
                return;
            }
            save(u, fp.getText().toString());
            showDashboard();
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(18);
        box.addView(go, lp);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(21, 21, 20));
        scroll.addView(box);
        setContentView(scroll);
    }

    private TextView text(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(Color.rgb(230, 230, 228));
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_LONG).show();
    }

    // ------------------------------------------------------------------ dashboard
    private void showDashboard() {
        final String url = prefs.getString("url", "");
        final String host = Uri.parse(url).getHost();
        if (web != null) web.destroy();
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(21, 21, 20));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                String want = prefs.getString("fp", "");
                String got = fingerprint(error.getCertificate());
                // only the dashboard itself, and only with the certificate from the QR code
                if (!want.isEmpty() && want.equals(got) && host != null && host.equals(Uri.parse(error.getUrl()).getHost())) {
                    handler.proceed();
                } else {
                    handler.cancel();
                    showSetup(want.isEmpty()
                            ? "This dashboard uses its own certificate. Scan the QR code in Settings → Phone app (or enter the fingerprint) so the app can check it."
                            : "The server's certificate doesn't match the one from your QR code. If you made a new certificate, scan the QR code again. Otherwise someone may be pretending to be your server.");
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (host != null && host.equals(u.getHost()) && "https".equals(u.getScheme())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));   // GitHub, Discord, ntfy links... open outside
                } catch (Exception ignored) {
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    showSetup("Can't reach " + url + " (" + err.getDescription() + "). Is the computer on and the phone on the same "
                            + "Wi-Fi? If the computer's address changed, scan the QR code again.");
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                try {
                    Intent pick = new Intent(Intent.ACTION_GET_CONTENT);
                    pick.addCategory(Intent.CATEGORY_OPENABLE);
                    pick.setType("*/*");
                    pick.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                    startActivityForResult(Intent.createChooser(pick, "Choose mod files"), PICK_FILE);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        web.setDownloadListener((dl, ua, cd, mime, len) -> toast("Downloads (exports, backups) work in the browser on your computer."));
        web.setOnLongClickListener(v -> {
            if (web.getHitTestResult().getType() == WebView.HitTestResult.UNKNOWN_TYPE) {
                new AlertDialog.Builder(this)
                        .setTitle("Server")
                        .setMessage(url)
                        .setPositiveButton("Change server", (d, w) -> showSetup(null))
                        .setNegativeButton("Reload", (d, w) -> web.reload())
                        .show();
                return true;
            }
            return false;
        });
        setContentView(web);
        web.loadUrl(url);
    }

    private static String fingerprint(SslCertificate cert) {
        try {
            X509Certificate x = cert.getX509Certificate();
            if (x == null) return "";
            byte[] d = MessageDigest.getInstance("SHA-256").digest(x.getEncoded());
            StringBuilder sb = new StringBuilder();
            for (byte b : d) sb.append(String.format(Locale.ROOT, "%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    @Override
    protected void onActivityResult(int req, int result, Intent data) {
        if (req == PICK_FILE && fileCallback != null) {
            Uri[] picked = null;
            if (result == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount();
                    picked = new Uri[n];
                    for (int i = 0; i < n; i++) picked[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    picked = new Uri[]{data.getData()};
                }
            }
            fileCallback.onReceiveValue(picked);
            fileCallback = null;
            return;
        }
        super.onActivityResult(req, result, data);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
