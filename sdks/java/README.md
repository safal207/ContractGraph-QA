# ContractGraph-QA interop report adapter for Java/JVM

This Java 17 library validates the complete pinned `cgqa-liminalqa-v0.1`
report. Jackson strict duplicate detection runs before semantic validation;
unknown fields, pin drift, missing cases, side-effect claims, and authority
escalation fail closed.

After Maven Central publication:

```xml
<dependency>
  <groupId>io.github.safal207</groupId>
  <artifactId>contractgraph-interop</artifactId>
  <version>0.1.0</version>
</dependency>
```

```java
var summary = InteropReportValidator.validate(reportBytes);
System.out.println(summary.passed());             // 14
System.out.println(summary.mayAuthorizeAction()); // false
```

Until publication, build locally with `mvn -f sdks/java/pom.xml package`.
A valid summary is conformance evidence only and cannot authorize an action.
