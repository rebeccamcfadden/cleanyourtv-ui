"""Run the real Images boundary with fake streams/HTTP, never the network."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_ui_home_preview import STUBS as DRAWING_STUBS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui/Images.java"
STUBS = {key: value for key, value in DRAWING_STUBS.items() if key.startswith("android/graphics/")}
STUBS.update({
    "android/content/Context.java": """
package android.content;
public class Context {
    public Context getApplicationContext() {return this;}
    public java.io.File getCacheDir() {return new java.io.File(System.getProperty("java.io.tmpdir"),"watch-next-art-test");}
    public ContentResolver getContentResolver() {return new ContentResolver();}
}
""",
    "android/content/ContentResolver.java": """
package android.content;
import java.io.*;
public class ContentResolver {
    public static final java.util.List<String> opened=new java.util.ArrayList<>();
    public InputStream openInputStream(android.net.Uri uri) throws IOException {
        String value=uri.toString();opened.add(value);
        if(value.contains("denied"))throw new SecurityException("private-token-do-not-log");
        if(value.contains("missing"))return null;
        return new ByteArrayInputStream(new byte[]{1,2,3});
    }
}
""",
    "android/content/res/Resources.java": """
package android.content.res;
public class Resources {public static class NotFoundException extends RuntimeException {}}
""",
    "android/net/Uri.java": """
package android.net;
public class Uri {
    final String value;
    Uri(String value) {this.value=value;}
    public static Uri parse(String value) {return new Uri(value);}
    public String getScheme() {int i=value.indexOf(':');return i<0?null:value.substring(0,i);}
    public String toString() {return value;}
}
""",
    "android/graphics/Bitmap.java": """
package android.graphics;
public class Bitmap {
    public enum Config {ARGB_8888,RGB_565}
    final int width,height;
    public Bitmap(int width,int height) {this.width=width;this.height=height;}
    public int getWidth() {return width;}
    public int getHeight() {return height;}
    public int getByteCount() {return width*height*2;}
    public static Bitmap createScaledBitmap(Bitmap from,int width,int height,boolean filter) {return new Bitmap(width,height);}
}
""",
    "android/graphics/BitmapFactory.java": """
package android.graphics;
public class BitmapFactory {
    public static class Options {
        public boolean inJustDecodeBounds;
        public int inSampleSize=1,outWidth,outHeight;
        public Bitmap.Config inPreferredConfig;
    }
    public static Bitmap decodeStream(java.io.InputStream stream,Rect padding,Options options) {
        options.outWidth=4000;options.outHeight=2000;
        return options.inJustDecodeBounds?null:new Bitmap(4000/options.inSampleSize,2000/options.inSampleSize);
    }
    public static Bitmap decodeByteArray(byte[] bytes,int start,int size,Options options) {
        return bytes[0]==0?null:new Bitmap(1600,900);
    }
    public static Bitmap decodeFile(String name,Options options) {
        try {return java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(name))[0]==0?null:new Bitmap(1600,900);}
        catch(java.io.IOException e){return null;}
    }
}
""",
    "android/os/Looper.java": """
package android.os;
public class Looper {public static Looper getMainLooper(){return new Looper();}}
""",
    "android/os/Handler.java": """
package android.os;
public class Handler {public Handler(Looper looper){} public boolean post(Runnable task){task.run();return true;}}
""",
    "android/util/LruCache.java": """
package android.util;
public class LruCache<K,V> {
    final java.util.Map<K,V> values=new java.util.concurrent.ConcurrentHashMap<>();
    public LruCache(int size){}
    protected int sizeOf(K key,V value){return 1;}
    public V get(K key){return values.get(key);}
    public V put(K key,V value){return values.put(key,value);}
    public void evictAll(){values.clear();}
}
""",
    "android/widget/ImageView.java": """
package android.widget;
public class ImageView {
    Object tag;
    public android.content.Context getContext(){return new android.content.Context();}
    public void setTag(Object value){tag=value;}
    public Object getTag(){return tag;}
    public void setImageBitmap(android.graphics.Bitmap bitmap){}
    public void setImageDrawable(android.graphics.drawable.Drawable drawable){}
}
""",
    "io/cleanyourtv/ui/ArtworkTest.java": """
package io.cleanyourtv.ui;
import android.graphics.Bitmap;
import android.content.*;
import java.io.*;
import java.net.*;
import java.util.concurrent.*;
class AppLog {
    static final java.util.List<String> logs=new java.util.ArrayList<>();
    static void w(String text){logs.add(text);}
}
class Tmdb {
    static byte[] readBytes(InputStream stream) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        int next;while((next=stream.read())!=-1)out.write(next);
        return out.toByteArray();
    }
}
public class ArtworkTest {
    static int requests;
    static Bitmap load(String poster,String thumbnail) throws Exception {
        Bitmap[] result=new Bitmap[1];CountDownLatch finished=new CountDownLatch(1);
        Images.loadArtwork(new Context(),poster,thumbnail,bitmap->{result[0]=bitmap;finished.countDown();});
        if(!finished.await(10,TimeUnit.SECONDS))throw new AssertionError("Artwork callback was lost");
        return result[0];
    }
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    public static void main(String[] args) throws Exception {
        URL.setURLStreamHandlerFactory(scheme->"https".equals(scheme)?new URLStreamHandler(){
            protected URLConnection openConnection(URL url){return new HttpURLConnection(url){
                public void disconnect(){}
                public boolean usingProxy(){return false;}
                public void connect(){}
                public InputStream getInputStream(){
                    requests++;
                    return new ByteArrayInputStream(new byte[]{(byte)(url.getPath().contains("bad")?0:1)});
                }
            };}
        }:null);
        try {
            switch(args[0]){
            case "https":
                Bitmap remote=load("https://example.invalid/image",null);
                check(remote!=null&&remote.getWidth()<=1024&&remote.getHeight()<=576,"HTTP artwork bounded");
                check(requests==1,"existing HTTP fetch reused");
                check(load("https://example.invalid/image",null)==remote&&requests==1,"memory cache reused");
                break;
            case "native":
                for(String scheme:new String[]{"content://provider/item","android.resource://test.player/123"}){
                    Bitmap nativeImage=load(scheme,null);
                    check(nativeImage!=null&&nativeImage.getWidth()<=1024&&nativeImage.getHeight()<=576,"sampled native artwork");
                    check(ContentResolver.opened.contains(scheme),"native API receives original URI unchanged");
                }
                check(requests==0,"native URIs never sent to HTTP");
                break;
            case "fallback":
                check(load("content://denied/private-token-do-not-log","android.resource://test.player/123")!=null,"poster failure falls back to thumbnail");
                check(load("https://example.invalid/bad","content://provider/thumbnail")!=null,"failed remote decode uses thumbnail");
                check(load(null,"content://provider/thumbnail")!=null,"missing poster uses thumbnail");
                break;
            case "failure":
                check(load(null,null)==null,"missing artwork stays absent");
                check(load("content://missing/item",null)==null,"unavailable artwork callback, not a crash");
                check(load("file:///private-token-do-not-log",null)==null,"unsupported scheme reported");
                check(!AppLog.logs.isEmpty(),"failures are explicit");
                check(AppLog.logs.stream().noneMatch(x->x.contains("private-token")||x.contains("content://")||x.contains("file:")),"no raw URLs or exception messages logged");
                break;
            }
        } finally {
            java.lang.reflect.Field field=Images.class.getDeclaredField("POOL");field.setAccessible(true);
            ExecutorService pool=(ExecutorService)field.get(null);pool.shutdownNow();pool.awaitTermination(5,TimeUnit.SECONDS);
        }
    }
}
""",
})


class WatchNextArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("JAVA_HOME")
        javac = str(Path(home) / "bin/javac") if home else shutil.which("javac")
        java = str(Path(home) / "bin/java") if home else shutil.which("java")
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        platforms = sorted((Path(sdk) / "platforms").glob("android-*/android.jar")) if sdk else []
        if not javac or not java or not platforms:
            raise unittest.SkipTest("JDK and Android SDK required for artwork tests")
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        sources = [str(SOURCE)]
        for name, text in STUBS.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            sources.append(str(path))
        compiled = subprocess.run(
            [javac, "--release", "8", "-cp", str(platforms[-1]), "-d", str(root), *sources],
            capture_output=True, text=True,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        cls.command = [java, "-cp", str(root) + os.pathsep + str(platforms[-1]),
                       "io.cleanyourtv.ui.ArtworkTest"]

    def run_case(self, case):
        with tempfile.TemporaryDirectory() as cache:
            tested = subprocess.run(
                self.command[:1] + ["-Djava.io.tmpdir=" + cache] + self.command[1:] + [case],
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)

    def test_https_and_existing_cache(self): self.run_case("https")
    def test_content_and_android_resource_artwork(self): self.run_case("native")
    def test_poster_then_thumbnail_fallback(self): self.run_case("fallback")
    def test_missing_and_failed_artwork(self): self.run_case("failure")


if __name__ == "__main__":
    unittest.main()
