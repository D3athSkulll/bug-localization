import java.io.*;
import java.util.*;
import org.jacoco.agent.rt.IAgent;
import org.jacoco.agent.rt.RT;
import org.jacoco.core.analysis.*;
import org.jacoco.core.data.*;
import org.junit.runner.*;
import org.junit.runner.notification.*;

/**
 * Runs JUnit test classes under the JaCoCo agent (output=none) and records, for every test method,
 * pass/fail and the set of covered source lines of the classes in classesDir.
 * Output format (tab separated):  T<TAB>test<TAB>PASS|FAIL   then   C<TAB>relative/File.java<TAB>l1,l2,...
 * args: classesDir outFile testClass...
 */
public class CoverageRunner {
    static File classesDir;
    static PrintWriter out;
    static Set<String> failed = new HashSet<String>();
    static long testNs = 0, dumpNs = 0, analyzeNs = 0, startNs; static int nTests = 0;

    public static void main(String[] a) throws Exception {
        classesDir = new File(a[0]);
        out = new PrintWriter(new OutputStreamWriter(new FileOutputStream(a[1]), "UTF-8"));
        final IAgent agent = RT.getAgent();
        startNs = System.nanoTime();
        JUnitCore core = new JUnitCore();
        core.addListener(new RunListener() {
            String cur; long t0;
            public void testStarted(Description d) { agent.reset(); cur = d.getDisplayName(); t0 = System.nanoTime(); }
            public void testFailure(Failure f) { failed.add(f.getDescription().getDisplayName()); }
            public void testAssumptionFailure(Failure f) { }
            public void testFinished(Description d) throws Exception {
                long t1 = System.nanoTime(); testNs += t1 - t0;
                byte[] data = agent.getExecutionData(true);
                long t2 = System.nanoTime(); dumpNs += t2 - t1;
                dump(d.getDisplayName(), data);
                analyzeNs += System.nanoTime() - t2; nTests++;
            }
        });
        for (int i = 2; i < a.length; i++) {
            Class<?> c = Class.forName(a[i]);
            if (java.lang.reflect.Modifier.isAbstract(c.getModifiers())) continue; // abstract bases are not runnable tests
            core.run(c);
        }
        out.println("M	" + nTests + "	" + testNs / 1000000 + "	" + dumpNs / 1000000 + "	" + analyzeNs / 1000000
            + "	" + (System.nanoTime() - startNs) / 1000000);   // tests, test_ms, jacoco_dump_ms, analyze_ms, total_ms
        out.close();
        System.exit(0);
    }

    static void dump(String test, byte[] data) throws Exception {
        ExecutionDataStore store = new ExecutionDataStore();
        SessionInfoStore si = new SessionInfoStore();
        ExecutionDataReader r = new ExecutionDataReader(new ByteArrayInputStream(data));
        r.setExecutionDataVisitor(store);
        r.setSessionInfoVisitor(si);
        r.read();
        CoverageBuilder cb = new CoverageBuilder();
        new Analyzer(store, cb).analyzeAll(classesDir);
        out.println("T\t" + test + "\t" + (failed.contains(test) ? "FAIL" : "PASS"));
        for (IClassCoverage cc : cb.getClasses()) {
            if (cc.getName().contains("$") ) { /* inner classes are merged by source file below */ }
        }
        Map<String, TreeSet<Integer>> perFile = new TreeMap<String, TreeSet<Integer>>();
        for (IClassCoverage cc : cb.getClasses()) {
            String pkg = cc.getPackageName();
            String file = (pkg.isEmpty() ? "" : pkg + "/") + cc.getSourceFileName();
            TreeSet<Integer> s = perFile.get(file);
            if (s == null) { s = new TreeSet<Integer>(); perFile.put(file, s); }
            for (int l = cc.getFirstLine(); l <= cc.getLastLine() && l > 0; l++) {
                int st = cc.getLine(l).getStatus();
                if (st == ICounter.FULLY_COVERED || st == ICounter.PARTLY_COVERED) s.add(l);
            }
        }
        for (Map.Entry<String, TreeSet<Integer>> e : perFile.entrySet()) {
            if (e.getValue().isEmpty()) continue;
            StringBuilder sb = new StringBuilder("C\t" + e.getKey() + "\t");
            boolean first = true;
            for (int l : e.getValue()) { if (!first) sb.append(','); sb.append(l); first = false; }
            out.println(sb);
        }
    }
}
