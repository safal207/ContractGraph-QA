# التشغيل البيني لـ ContractGraph-QA: دليل في خمس دقائق

[English](../en/GETTING_STARTED.md) · [简体中文](../zh-CN/GETTING_STARTED.md) · [हिन्दी](../hi/GETTING_STARTED.md) · [Español](../es/GETTING_STARTED.md) · العربية

تكوّن ContractGraph-QA وLiminalQA وPythiaLabs منظومة أمان تعتمد على الأدلة
لسير عمل الوكلاء ذي الحالة وعالي المخاطر. يحتفظ كل مشروع بسلطة قراره، وتتبادل
المهايئات أدلة JSON صارمة من دون تحويل التقرير إلى إذن بتنفيذ أي إجراء.

## دور كل مشروع

| المشروع | الدور | ما لا يدّعيه |
|---|---|---|
| ContractGraph-QA | بحث محدود في الحالات والإجراءات، وأدلة مرتبطة بالهدف الدقيق، ومدخلات لإعادة التشغيل | إثبات صحة شامل أو سلطة تنفيذ الإجراء |
| LiminalQA | سياق QA ثنائي الزمن ومرشحات غير ملزمة لإعادة التشغيل ودَين التحقق | finding مؤكدة من CGQA أو حكم استمرارية LTP |
| PythiaLabs | بوابة تفويض حتمية جديدة تستخدم الدليل الخارجي كسياق استشاري | أن الدليل الخارجي وحده يستطيع إرجاع `ALLOW` |

## تشغيل العقد المثبّت

من نسخة محلية من ContractGraph-QA:

```bash
python -m pip install .
cgqa liminalqa-conformance > report.json
```

يحتوي التقرير الناجح على جميع متجهات الاختبار الأربعة عشر، الذهبية وتلك التي
تغلق عند الفشل:

```json
{"status":"PASS","counts":{"total":14,"passed":14,"failed":0},"authority":{"classification":"conformance_evidence_only","mayAuthorizeAction":false}}
```

كما يثبّت التقرير الكامل SHA-256 للحزمة، وعقدَي المنتج، ومعرّف كل حالة وبصمة
مدخلها، و`sideEffectExecuted=false` وحدود الادعاء.

## التحقق بلغتك البرمجية

يوفر المستودع مهايئات خفيفة لـ TypeScript/JavaScript وGo وJava/JVM و.NET.
تتحقق هذه المهايئات من دليل المشغّل الأصلي ولا تعيد تنفيذ منطق قرارات
CGQA/LiminalQA.

```bash
node sdks/typescript/bin/cgqa-report-validate.js report.json

cd sdks/go && go run ./cmd/cgqa-report-validate ../../report.json

mvn -q -f sdks/java/pom.xml exec:java -Dexec.args=report.json

dotnet run --project sdks/dotnet/src/ContractGraphQA.Interop.Cli -- report.json
```

توجد إحداثيات الحزم وطرق الربط المحلي في [دليل إصدار SDK](../../SDK_RELEASE.md).
Python هو المشغّل المرجعي لـ ContractGraph-QA، وRust هو المشغّل الأصلي لـ
LiminalQA، وElixir هو المشغّل الأصلي لـ PythiaLabs.

[يتوفر SDK v0.1.0 للتنزيل العام من GitHub](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0)،
كما يمكن تثبيت وحدة Go بالأمر
`go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0`. تتوفر ملفات
`.tgz` وJAR/POM و`.nupkg` ضمن الإصدار؛ أما النشر على npm وMaven Central
وnuget.org فما زال بانتظار الإعداد.

## حدود الإغلاق الآمن

ترفض جميع المهايئات مفاتيح JSON المكررة، والحقول الحرجة غير المعروفة، وتغيّر
أي pin، والحالات المفقودة أو المكررة، و`UNSAFE_ACCEPTED`، و
`mayAuthorizeAction=true`، وأي أثر جانبي مُعلن. الحد الأقصى للمدخل 1 MiB، ولا
يجري التحقق اتصالاً شبكياً أو تنفيذ مرشح أو كتابة قاعدة بيانات أو إجراءً على
النظام الهدف.

يعني التقرير الصالح فقط أن التنفيذ طابق المتجهات الاصطناعية المثبّتة. قبل أي
إجراء حقيقي، أعد التحقق من الهدف الدقيق باستخدام الأدلة الحالية وشغّل بوابة
Pythia أو بوابة المشغّل الفعالة. `PASS` ليس إذناً أبداً.

البروتوكول الكامل: [التشغيل البيني ContractGraph-QA ↔ LiminalQA](../../LIMINALQA_INTEROP.md).
