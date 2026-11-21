# Roadmap

What we're working on, what's next, and what we're still deciding. Priorities come from the people
using PromptVeil, so **vote with 👍** on the linked issues and Discussions, and add what's missing in the
[detector request thread](https://github.com/total-tensor-lab/PromptVeil/discussions/53).

Many items are tagged
[`good first issue`](https://github.com/total-tensor-lab/PromptVeil/labels/good%20first%20issue).
Comment on one to claim it.

> PromptVeil helps with privacy regulations such as HIPAA and GDPR, but it doesn't make an application
> compliant and isn't legal advice. See the disclaimer in the [README](README.md#compliance-profiles).

## Now

**HIPAA identifier coverage** ([`hipaa`](https://github.com/total-tensor-lab/PromptVeil/labels/hipaa))
Fill in more of the Safe Harbor identifiers that the `us_hipaa` profile is missing.

- IP addresses [#68](https://github.com/total-tensor-lab/PromptVeil/issues/68) and URLs [#69](https://github.com/total-tensor-lab/PromptVeil/issues/69)
- Medicare Beneficiary Identifier [#70](https://github.com/total-tensor-lab/PromptVeil/issues/70), NPI [#71](https://github.com/total-tensor-lab/PromptVeil/issues/71), DEA number [#72](https://github.com/total-tensor-lab/PromptVeil/issues/72), VIN [#73](https://github.com/total-tensor-lab/PromptVeil/issues/73)
- Medical record numbers [#74](https://github.com/total-tensor-lab/PromptVeil/issues/74) and dates of birth [#75](https://github.com/total-tensor-lab/PromptVeil/issues/75), detected from nearby keywords
- Export `USDetector` [#54](https://github.com/total-tensor-lab/PromptVeil/issues/54)
- Expand the `us_hipaa` profile with all of the above [#76](https://github.com/total-tensor-lab/PromptVeil/issues/76)

**EU and UK national IDs for GDPR** ([`gdpr`](https://github.com/total-tensor-lab/PromptVeil/labels/gdpr))

- France NIR [#60](https://github.com/total-tensor-lab/PromptVeil/issues/60), Spain DNI / NIE [#61](https://github.com/total-tensor-lab/PromptVeil/issues/61), Italy Codice Fiscale [#62](https://github.com/total-tensor-lab/PromptVeil/issues/62), Netherlands BSN [#63](https://github.com/total-tensor-lab/PromptVeil/issues/63)
- Poland PESEL [#77](https://github.com/total-tensor-lab/PromptVeil/issues/77), Sweden personnummer [#78](https://github.com/total-tensor-lab/PromptVeil/issues/78), Germany Steuer-ID [#79](https://github.com/total-tensor-lab/PromptVeil/issues/79), Belgium national number [#80](https://github.com/total-tensor-lab/PromptVeil/issues/80)
- IBAN [#67](https://github.com/total-tensor-lab/PromptVeil/issues/67) and EU VAT numbers [#81](https://github.com/total-tensor-lab/PromptVeil/issues/81)
- UK National Insurance number [#55](https://github.com/total-tensor-lab/PromptVeil/issues/55) and NHS number [#56](https://github.com/total-tensor-lab/PromptVeil/issues/56) (UK GDPR)
- Expand the `eu_gdpr` profile with the EU IDs [#82](https://github.com/total-tensor-lab/PromptVeil/issues/82)

## Next

**More privacy laws**

- Canada SIN, PIPEDA [#57](https://github.com/total-tensor-lab/PromptVeil/issues/57)
- Australia TFN, Privacy Act [#58](https://github.com/total-tensor-lab/PromptVeil/issues/58)
- Brazil CPF, LGPD [#59](https://github.com/total-tensor-lab/PromptVeil/issues/59)
- Singapore NRIC / FIN, PDPA [#64](https://github.com/total-tensor-lab/PromptVeil/issues/64)
- South Africa ID, POPIA [#65](https://github.com/total-tensor-lab/PromptVeil/issues/65)
- Mexico CURP, LFPDPPP [#66](https://github.com/total-tensor-lab/PromptVeil/issues/66)

**EU AI Act record-keeping** ([`eu-ai-act`](https://github.com/total-tensor-lab/PromptVeil/labels/eu-ai-act), vote in [#83](https://github.com/total-tensor-lab/PromptVeil/discussions/83))

- Audit-log export: a versioned schema, retention settings, request IDs, optional tamper evidence
- An `eu_ai_act` profile that combines the GDPR detectors with logging defaults

## Exploring

Not committed yet. Vote and comment in the linked Discussions to move an item up.

- Scanning datasets and RAG corpora for personal data before indexing or training ([#83](https://github.com/total-tensor-lab/PromptVeil/discussions/83), idea 3)
- A `review` policy action that holds a prompt for human approval ([#83](https://github.com/total-tensor-lab/PromptVeil/discussions/83), idea 4)
- AI-interaction disclosure for responses ([#83](https://github.com/total-tensor-lab/PromptVeil/discussions/83), idea 5)
- NLP-based detection for names, street addresses and GDPR Art. 9 special-category data ([#53](https://github.com/total-tensor-lab/PromptVeil/discussions/53))
- Your idea: post it in [Ideas](https://github.com/total-tensor-lab/PromptVeil/discussions/categories/ideas)
