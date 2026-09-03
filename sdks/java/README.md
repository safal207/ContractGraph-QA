# ContractGraph-QA interop report adapter for Java/JVM

This Java 17 library validates the complete pinned `cgqa-liminalqa-v0.1`
report. Jackson strict duplicate detection runs before semantic validation;
unknown fields, pin drift, missing cases, side-effect claims, and authority
escalation fail closed.

The dependency coordinate will be usable as follows after Maven Central
publication:

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

For v0.1.0, download the public JAR and POM and install them in the local Maven
repository:

```bash
curl -fLO https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-interop-0.1.0.jar
curl -fLO https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-interop-0.1.0.pom
mvn install:install-file \
  -Dfile=contractgraph-interop-0.1.0.jar \
  -DpomFile=contractgraph-interop-0.1.0.pom
```

The coordinate is not listed in Maven Central yet. From a repository checkout,
you can alternatively run `mvn -f sdks/java/pom.xml package`.
A valid summary is conformance evidence only and cannot authorize an action.
