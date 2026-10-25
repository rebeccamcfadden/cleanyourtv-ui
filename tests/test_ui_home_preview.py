"""Compile the real preview layout against Android APIs; test geometry without a device/runtime."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui/HomePreview.java"
STUBS = {
    "android/graphics/RectF.java": """
package android.graphics;
public class RectF {
    public float left,top,right,bottom;
    public void set(float l,float t,float r,float b) {left=l;top=t;right=r;bottom=b;}
    public float width() {return right-left;}
    public float height() {return bottom-top;}
    public float centerX() {return (left+right)/2;}
    public float centerY() {return (top+bottom)/2;}
}
""",
    "io/cleanyourtv/ui/Ui.java": """
package io.cleanyourtv.ui;
import android.graphics.*;
class Ui {
    static Typeface medium, regular, light;
    static Paint text(Typeface face,float size,int color) {throw new AssertionError("No drawing in geometry tests");}
    static Paint numbers(Typeface face,float size,int color) {return text(face,size,color);}
    static String tr(String pt,String en) {return en;}
    static int alpha(int color,float alpha) {return color;}
    static float clamp(float value) {return Math.min(1,Math.max(0,value));}
    static float halfCap(Paint paint) {return 10;}
}
""",
    "io/cleanyourtv/ui/Spare.java": """
package io.cleanyourtv.ui;
class Spring {float value;}
class Symbols {
    static void draw(android.content.Context context,android.graphics.Canvas c,String name,
        float x,float y,float size,int color) {}
}
""",
    "io/cleanyourtv/ui/PreviewTest.java": """
package io.cleanyourtv.ui;
import android.graphics.RectF;
public class PreviewTest {
    static void check(boolean condition,String message) {if (!condition) throw new AssertionError(message);}
    public static void main(String[] args) {
        for (float k : new float[]{0.5f, 2f/3, 1f, 2f}) {
            RectF[] cards=new RectF[HomePreview.COUNT], top=new RectF[HomePreview.TOP_COUNT];
            for(int i=0;i<cards.length;i++)cards[i]=new RectF();
            for(int i=0;i<top.length;i++)top[i]=new RectF();
            HomePreview.layoutCards(cards,k);
            HomePreview.layoutTop(top,k);
            for(int i=0;i<cards.length;i++) {
                check(cards[i].top>178*k && cards[i].bottom+80*k<1080*k,"cards and metadata visible at Home");
                if(i>0)check(cards[i].left>cards[i-1].right,"cards do not overlap");
            }
            check(HomePreview.APPS_TOP>1080,"apps start strictly below the Home viewport");
            float apps=HomePreview.APPS_TOP-HomePreview.APPS_SCROLL;
            check(apps>178 && apps+188<1080,"apps and labels visible when focused");
            check(HomePreview.APPS_TOP<HomePreview.UTILITIES_TOP &&
                HomePreview.UTILITIES_TOP<HomePreview.WEATHER_TOP,"apps above utilities above weather");
            check(HomePreview.UTILITIES_TOP-HomePreview.UTILITIES_SCROLL>178,"utilities below sticky header");
            check(HomePreview.WEATHER_TOP-HomePreview.UTILITIES_SCROLL+300<1080,"full weather card fits");
            for(int i=0;i<top.length;i++) {
                check(top[i].left>=80*k && top[i].right<=1840*k,"header safe margins");
                if(i>0)check(top[i].left>top[i-1].right,"header items do not overlap");
            }
        }
        check(HomePreview.placeholderMessage().contains("not connected"),"placeholder action is explicit");
        check(HomePreview.demo().equals("Demo"),"sample identification");
    }
}
""",
}


class HomePreviewTests(unittest.TestCase):
    def test_scaled_geometry_and_placeholder_labels(self):
        home = os.environ.get("JAVA_HOME")
        javac = str(Path(home) / "bin/javac") if home else shutil.which("javac")
        java = str(Path(home) / "bin/java") if home else shutil.which("java")
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        platforms = sorted((Path(sdk) / "platforms").glob("android-*/android.jar")) if sdk else []
        if not javac or not java or not platforms:
            self.skipTest("JDK and Android SDK required for Home preview geometry tests")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = [str(SOURCE)]
            for name, text in STUBS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                sources.append(str(path))
            compiled = subprocess.run(
                [javac, "--release", "8", "-cp", str(platforms[-1]), "-d", directory, *sources],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            tested = subprocess.run(
                [java, "-cp", directory + os.pathsep + str(platforms[-1]), "io.cleanyourtv.ui.PreviewTest"],
                capture_output=True, text=True,
            )
            self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)


if __name__ == "__main__":
    unittest.main()
