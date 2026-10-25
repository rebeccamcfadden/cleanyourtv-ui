"""Exercise the existing Home renderer and real native items with a recording Canvas."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui/HomePreview.java"
STUBS = {
    "android/content/Context.java": """
package android.content;
public class Context {
    public android.content.pm.PackageManager getPackageManager() {return null;}
}
""",
    "android/graphics/Shader.java": """
package android.graphics;
public class Shader {public enum TileMode {CLAMP}}
""",
    "android/graphics/LinearGradient.java": """
package android.graphics;
public class LinearGradient extends Shader {
    public LinearGradient(float a,float b,float c,float d,int e,int f,TileMode mode) {}
}
""",
    "android/graphics/Bitmap.java": """
package android.graphics;
public class Bitmap {
    public int getWidth() {return 800;}
    public int getHeight() {return 450;}
}
""",
    "android/graphics/Paint.java": """
package android.graphics;
public class Paint {
    public static final int ANTI_ALIAS_FLAG=1;
    public enum Style {STROKE}
    public int alpha=255;
    public float size=20;
    public Paint(int flags) {}
    public void setStyle(Style style) {}
    public void setColor(int color) {alpha=color>>>24;}
    public void setShader(Shader shader) {}
    public void setAlpha(int value) {alpha=value;}
    public void setStrokeWidth(float width) {}
    public void setTextSize(float value) {size=value;}
    public void setFilterBitmap(boolean value) {}
    public float measureText(String text) {return text.length()*size/2;}
    public int breakText(String text,boolean forward,float width,float[] measured) {
        return Math.min(text.length(),Math.max(0,(int)(width/(size/2))));
    }
}
""",
    "android/graphics/Path.java": """
package android.graphics;
public class Path {
    public enum Direction {CW}
    public void reset() {}
    public void moveTo(float x,float y) {}
    public void lineTo(float x,float y) {}
    public void close() {}
    public void addRoundRect(RectF box,float a,float b,Direction direction) {}
}
""",
    "android/graphics/Canvas.java": """
package android.graphics;
import java.util.*;
public class Canvas {
    public final List<String> texts=new ArrayList<>();
    public final List<Float> progress=new ArrayList<>();
    public int bitmaps, cards, skyAlpha=-1;
    public void save() {}
    public void restore() {}
    public void scale(float x,float y) {}
    public void clipPath(Path path) {}
    public void drawText(String text,float x,float y,Paint paint) {texts.add(text);}
    public void drawRect(float a,float b,float c,float d,Paint paint) {if(a==0&&b==0&&d==1080&&skyAlpha==-1)skyAlpha=paint.alpha;}
    public void drawRect(RectF box,Paint paint) {}
    public void drawPath(Path path,Paint paint) {}
    public void drawRoundRect(RectF box,float a,float b,Paint paint) {cards++;}
    public void drawRoundRect(float a,float b,float c,float d,float e,float f,Paint paint) {
        if(b==861&&d==866)progress.add(c-a);
    }
    public void drawBitmap(Bitmap bitmap,android.graphics.Rect from,RectF to,Paint paint) {bitmaps++;}
}
""",
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
    static Paint text(Typeface face,float size,int color) {Paint p=new Paint(1);p.setTextSize(size);p.setColor(color);return p;}
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
class ContinueWatchingPlayback {
    enum LaunchResult {STARTED, INVALID_INTENT, UNAVAILABLE, FAILED}
    static ContinueWatchingItem launched;
    static LaunchResult outcome=LaunchResult.STARTED;
    ContinueWatchingPlayback(android.content.pm.PackageManager packages) {}
    LaunchResult launch(android.content.Context context,ContinueWatchingItem item) {launched=item;return outcome;}
}
""",
    "io/cleanyourtv/ui/PreviewTest.java": """
package io.cleanyourtv.ui;
import android.graphics.*;
import java.util.*;
public class PreviewTest {
    static void check(boolean condition,String message) {if (!condition) throw new AssertionError(message);}
    static ContinueWatchingItem item(long id,Long position,Long duration,String season,String episode,String title) {
        return item(id,position,duration,season,episode,title,ContinueWatchingItem.ContinuationKind.CONTINUE);
    }
    static ContinueWatchingItem item(long id,Long position,Long duration,String season,String episode,String title,
            ContinueWatchingItem.ContinuationKind kind) {
        return new ContinueWatchingItem(id,"Same title",null,"test.player","original:"+id,null,null,position,duration,
            null,season,episode,title,null,kind,
            ContinueWatchingItem.PlaybackCapability.VALID_PLAYBACK,null,null,null);
    }
    static ContinueWatchingItem item(long id) {return item(id,null,null,null,null,null);}
    static Canvas draw(HomeContinueWatching row,Bitmap first) {
        RectF[] rects=new RectF[HomeContinueWatching.VISIBLE];
        Spring[] focus=new Spring[rects.length];
        for(int i=0;i<rects.length;i++){rects[i]=new RectF();focus[i]=new Spring();}
        HomePreview.layoutCards(rects,1);
        Bitmap[] images=new Bitmap[rects.length];images[0]=first;
        Canvas c=new Canvas();
        new HomePreview().hero(c,1,"Hello","Date","Clock","",rects,focus,row,images);
        return c;
    }
    static void geometry() {
        for (float k : new float[]{0.5f, 2f/3, 1f, 2f}) {
            RectF[] cards=new RectF[HomeContinueWatching.VISIBLE], top=new RectF[HomePreview.TOP_COUNT];
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
    }
    public static void main(String[] args) {
        HomeContinueWatching row=new HomeContinueWatching();
        switch(args[0]) {
        case "geometry": geometry(); break;
        case "empty":
            check(row.isEmpty()&&row.visibleCount()==0&&row.current()==null,"empty row state");
            Canvas empty=draw(row,null);
            check(!empty.texts.contains("Continue Watching")&&empty.cards==0,"empty row omitted");
            row.update(Arrays.asList(item(1)));row.update(Collections.emptyList());
            check(draw(row,null).cards==0,"row disappears after refresh");
            break;
        case "cards":
            row.update(Arrays.asList(item(1)));
            Canvas one=draw(row,null);
            check(one.cards==1&&one.texts.contains("Same title")&&one.bitmaps==0,"one real card without artwork");
            row.select(20);check(row.selected()==0,"single card right edge");
            row.select(-1);check(row.selected()==0,"single card left edge");
            row.update(Arrays.asList(item(1),item(2),item(3),item(4),item(5)));
            check(draw(row,new Bitmap()).cards==4,"four-card existing viewport");
            row.select(4);check(row.first()==1&&row.selected()==4,"fifth item scrolls into view");
            check(draw(row,new Bitmap()).bitmaps==1,"loaded artwork drawn");
            row.select(500);check(row.selected()==4,"right edge");
            row.select(-1);check(row.selected()==0&&row.first()==0,"left edge");
            break;
        case "progress":
            row.update(Arrays.asList(item(1)));check(draw(row,null).progress.isEmpty(),"unknown progress hidden");
            row.update(Arrays.asList(item(1,0L,1429000L,null,null,null)));
            Canvas zero=draw(row,null);check(zero.texts.contains("0%")&&zero.progress.get(1)==0,"known zero remains visible zero");
            ContinueWatchingItem youtube=item(1,808000L,1429000L,null,null,null);
            row.update(Arrays.asList(youtube));Canvas real=draw(row,null);
            check(Math.abs(real.progress.get(1)/real.progress.get(0)-808000d/1429000)<0.00001,"real 56.5 percent geometry");
            check(real.texts.contains("56%"),"real progress label, no fake values");
            row.update(Arrays.asList(item(1,200L,100L,null,null,null)));
            check(draw(row,null).texts.contains("100%"),"completed display clamps");
            break;
        case "next":
            ContinueWatchingItem next=item(2,null,null,"2","1",null,ContinueWatchingItem.ContinuationKind.NEXT);
            check(next.canContinue(),"NEXT qualifies without fabricated progress");
            row.update(Arrays.asList(item(1),next));
            Canvas mixed=draw(row,null);
            check(mixed.cards==2&&mixed.progress.isEmpty(),"mixed CONTINUE/NEXT cards; unknown progress hidden");
            row.select(1);
            check(row.current()==next,"NEXT is focusable");
            check(row.launch(new android.content.Context())==ContinueWatchingPlayback.LaunchResult.STARTED
                && ContinueWatchingPlayback.launched==next,"NEXT dispatches original item through playback boundary");
            break;
        case "metadata":
            check(HomeContinueWatching.secondary(item(1)).isEmpty(),"no fabricated episode metadata");
            check(HomeContinueWatching.secondary(item(1,null,null,"2","4","Chapter")).equals("S2 E4 / Chapter"),"full episode");
            check(HomeContinueWatching.secondary(item(1,null,null,"Specials",null,null)).equals("SSpecials"),"season display string");
            check(HomeContinueWatching.secondary(item(1,null,null,null,"IV",null)).equals("EIV"),"episode display string");
            check(HomeContinueWatching.secondary(item(1,null,null,null,null,"Chapter")).equals("Chapter"),"episode title only");
            break;
        case "focus":
            ContinueWatchingItem a=item(1),b=item(2),c=item(3);
            row.update(Arrays.asList(a,b,c));row.select(1);
            ContinueWatchingItem updated=item(2,400L,1000L,null,null,null);
            row.update(Arrays.asList(updated,c,a));
            check(row.current()==updated&&row.selected()==0,"stable ID survives reorder with fresh metadata");
            row.update(Arrays.asList(c,a));check(row.current()==c,"removed focus uses nearest surviving index");
            row.select(1);row.update(Arrays.asList(c));check(row.current()==c,"last focused item removed");
            row.update(Collections.emptyList());check(row.isEmpty(),"no invalid focus when row disappears");
            break;
        case "failures":
            for(ContinueWatchingSource.Status status:new ContinueWatchingSource.Status[]{
                    ContinueWatchingSource.Status.PERMISSION_DENIED,ContinueWatchingSource.Status.UNAVAILABLE,
                    ContinueWatchingSource.Status.ERROR}) {
                row.update(Arrays.asList(item(1)));
                row.update(ContinueWatchingSource.Result.empty(status).items);
                check(row.isEmpty()&&draw(row,null).cards==0,"failure removes stale cards: "+status);
            }
            break;
        case "playback":
            ContinueWatchingItem target=item(42);row.update(Arrays.asList(target));
            android.content.Context context=new android.content.Context();
            check(row.launch(context)==ContinueWatchingPlayback.LaunchResult.STARTED,"dispatch result");
            check(ContinueWatchingPlayback.launched==target,"selected original item goes to Phase 2 playback");
            for(ContinueWatchingPlayback.LaunchResult failure:ContinueWatchingPlayback.LaunchResult.values()) {
                ContinueWatchingPlayback.outcome=failure;
                check(row.launch(context)==failure&&row.current()==target,"launch outcome leaves Home selection stable");
            }
            break;
        case "opacity":
            HomePreview renderer=new HomePreview();RectF[] rects=new RectF[8];Spring[] springs=new Spring[8];
            for(int i=0;i<8;i++){rects[i]=new RectF();springs[i]=new Spring();}
            HomePreview.layoutTop(rects,1);Canvas canvas=new Canvas();
            renderer.header(canvas,new android.content.Context(),1,rects,springs,1050);
            renderer.background(canvas,1);
            check(canvas.skyAlpha==255,"header paint alpha never leaks into background");
            break;
        default: throw new AssertionError(args[0]);
        }
    }
}
""",
}


class HomePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("JAVA_HOME")
        javac = str(Path(home) / "bin/javac") if home else shutil.which("javac")
        java = str(Path(home) / "bin/java") if home else shutil.which("java")
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        platforms = sorted((Path(sdk) / "platforms").glob("android-*/android.jar")) if sdk else []
        if not javac or not java or not platforms:
            raise unittest.SkipTest("JDK and Android SDK required for Home tests")
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        sources = [str(SOURCE), str(SOURCE.with_name("ContinueWatchingItem.java")),
                   str(SOURCE.with_name("HomeContinueWatching.java")),
                   str(SOURCE.with_name("ContinueWatchingSource.java"))]
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
        cls.command = [java, "-cp", str(root) + os.pathsep + str(platforms[-1]), "io.cleanyourtv.ui.PreviewTest"]

    def run_case(self, case):
        tested = subprocess.run(self.command + [case], capture_output=True, text=True)
        self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)

    def test_scaled_geometry(self): self.run_case("geometry")
    def test_empty_and_disappearing_row(self): self.run_case("empty")
    def test_one_and_multiple_real_cards(self): self.run_case("cards")
    def test_unknown_zero_real_and_completed_progress(self): self.run_case("progress")
    def test_next_and_continue_share_existing_row_and_playback(self): self.run_case("next")
    def test_partial_episode_metadata(self): self.run_case("metadata")
    def test_identity_focus_reorder_and_removal(self): self.run_case("focus")
    def test_selection_dispatch_and_failed_playback(self): self.run_case("playback")
    def test_shared_paint_opacity(self): self.run_case("opacity")
    def test_permission_and_provider_failures_omit_row(self): self.run_case("failures")

    def test_home_lifecycle_permission_navigation_and_playback_wiring(self):
        """Static wiring checks complement runtime row tests; not an Android lifecycle simulation."""
        home = SOURCE.with_name("HomeView.java").read_text(encoding="utf-8")
        settings = SOURCE.with_name("SettingsActivity.java").read_text(encoding="utf-8")
        self.assertEqual(home.count("new ContinueWatchingRepository("), 1)
        for call in ("continueRepository.addListener(continueListener)",
                     "continueRepository.removeListener(continueListener)",
                     "continueRepository.onForeground()", "continueRepository.onBackground()",
                     "continueRepository.close()", "continueRepository.current()",
                     "continueRow.update(result.items)", "continueRow.launch(activity)"):
            self.assertIn(call, home)
        self.assertNotIn("TvContract", home)
        self.assertNotIn("getContentResolver", home)
        self.assertNotIn("requestPermissions", home)
        self.assertNotIn("continueRepository.refresh()", home)
        self.assertIn('Prefs.continueWatching() && activity.checkSelfPermission("android.permission.READ_TV_LISTINGS")', home)
        self.assertIn("continueRepository.setFilters(Prefs.continueWatchingRecentOnly(), Prefs.continueWatchingHideFinished())", home)
        for key, setter in (("continue_watching_recent_only", "setContinueWatchingRecentOnly"),
                            ("continue_watching_hide_finished", "setContinueWatchingHideFinished")):
            self.assertIn(f'getBoolean("{key}", false)', SOURCE.with_name("Prefs.java").read_text(encoding="utf-8"))
            self.assertIn(setter, settings)
            self.assertIn(f'o.getBoolean("{key}")', SOURCE.with_name("TvConfig.java").read_text(encoding="utf-8"))
        self.assertIn("if (!continueRow.isEmpty()) zone = Z_CONTINUE", home)
        self.assertIn("else if (!shelf.isEmpty()) zone = Z_SHELF", home)
        self.assertIn("else openDrawer()", home)
        self.assertIn("zone = continueRow.isEmpty() ? Z_TOP : Z_CONTINUE", home)
        self.assertIn("case Z_CONTINUE:", home)
        self.assertIn("zone == Z_CONTINUE && continueRow.isEmpty()", home)
        self.assertIn("if (!previewHome || !playbackDispatched) reset(true)", home)
        self.assertIn("artworkGeneration != request", home)
        self.assertIn("if (!running", home)
        self.assertIn("requestPermissions(new String[] {TV_LISTINGS}, TV_LISTINGS_REQUEST)", settings)
        self.assertNotIn("ACCESS_ALL_EPG_DATA", settings)
        self.assertNotIn("WRITE_EPG_DATA", settings)
        for fixture in ("Severance", "Sample progress", "Demo only.", "Dune: Part Two"):
            self.assertNotIn(fixture, SOURCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
