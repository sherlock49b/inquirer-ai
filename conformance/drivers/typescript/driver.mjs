// Conformance driver (TypeScript/Node, ESM).
//
// Runs the 11-prompt conformance scenario against the REAL inquirer-ai library
// in STDIO AGENT MODE. The library reads answers from stdin and writes the
// JSONL protocol (handshake + prompts + validation_errors) to stdout. This
// driver collects each prompt's RETURN VALUE and writes them as a single JSON
// array to the file path given in argv[1] (the "results file").
//
// Run:
//   INQUIRER_AI_MODE=agent INQUIRER_AI_TRANSPORT=stdio \
//     node driver.mjs <results_file> < fixture.jsonl
//
// Protocol stays on stdout; the results array goes to the file.

import * as fs from "node:fs";
import {
  text,
  confirm,
  number,
  select,
  checkbox,
  rawlist,
  search,
  password,
  expand,
  autocomplete,
  path,
  createSeparator,
} from "/home/yinfeng/dev/inquirer-ai/typescript/dist/index.js";

async function main() {
  const resultsFile = process.argv[2];
  if (!resultsFile) {
    process.stderr.write("usage: node driver.mjs <results_file>\n");
    process.exit(2);
  }

  const results = [];

  // P1 text/input  message="Name"  default="anon"
  results.push(await text({ message: "Name", default: "anon" }));

  // P2 confirm  message="Proceed?"  default=true
  results.push(await confirm({ message: "Proceed?", default: true }));

  // P3 number  message="Count"  default=10  min=1  max=1000  float_allowed=false
  results.push(
    await number({
      message: "Count",
      default: 10,
      min: 1,
      max: 1000,
      floatAllowed: false,
    }),
  );

  // P4 select  message="Lang"
  results.push(
    await select({
      message: "Lang",
      choices: [
        { name: "Python", value: "py" },
        { name: "Go", value: "go" },
        createSeparator("--"),
        { name: "Rust", value: "rs", disabled: "soon" },
      ],
    }),
  );

  // P5 checkbox  message="Feat"  default=["a"]
  results.push(
    await checkbox({
      message: "Feat",
      default: ["a"],
      choices: [
        { name: "A", value: "a" },
        { name: "B", value: "b" },
        { name: "C", value: "c" },
      ],
    }),
  );

  // P6 rawlist  message="Ver"
  results.push(
    await rawlist({
      message: "Ver",
      choices: [
        { name: "3.13", value: "313" },
        createSeparator("-"),
        { name: "3.12", value: "312", disabled: true },
        { name: "3.11", value: "311" },
      ],
    }),
  );

  // P7 search  message="Pkg"
  // The library's search prompt takes a `source` function rather than a static
  // choices array; the resolved choices are advertised in the agent payload and
  // used to resolve the answer ("requests" -> "req").
  const pkgChoices = [
    { name: "requests", value: "req" },
    { name: "httpx", value: "hx" },
  ];
  results.push(
    await search({
      message: "Pkg",
      source: (term) => {
        if (!term) return pkgChoices;
        const t = term.toLowerCase();
        return pkgChoices.filter((c) => c.name.toLowerCase().includes(t));
      },
    }),
  );

  // P8 password  message="Token"  default="def"
  results.push(await password({ message: "Token", default: "def" }));

  // P9 expand  message="Conflict"  (key "Y" is uppercase ON PURPOSE -> lowercased)
  results.push(
    await expand({
      message: "Conflict",
      choices: [
        { key: "Y", name: "Yes", value: "yes" },
        { key: "n", name: "No", value: "no" },
      ],
    }),
  );

  // P10 autocomplete  message="Free"
  results.push(
    await autocomplete({ message: "Free", choices: ["Python", "Go"] }),
  );

  // P11 path  message="Dir"  default="."
  results.push(await path({ message: "Dir", default: "." }));

  fs.writeFileSync(resultsFile, JSON.stringify(results));
}

main().catch((err) => {
  process.stderr.write(`driver error: ${err && err.stack ? err.stack : err}\n`);
  process.exit(1);
});
