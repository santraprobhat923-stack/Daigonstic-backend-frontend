import fs from "node:fs";

import { generate } from "@pdfme/generator";
import {
  text,
  image,
  signature,
  table,
  line,
  rectangle,
  ellipse,
  svg,
  list,
  multiVariableText,
  date,
  dateTime,
  time,
  select,
  checkbox,
  radioGroup,
  circleMark,
} from "@pdfme/schemas";

const raw = fs.readFileSync(0, "utf8");
const job = JSON.parse(raw);

if (!job || !job.template || !Array.isArray(job.template.schemas)) {
  throw new Error("Invalid pdfme job: template.schemas is required");
}
if (!job.basePdf) {
  throw new Error("Invalid pdfme job: basePdf is required");
}

const template = {
  ...job.template,
  basePdf: job.basePdf,
};

const plugins = {
  text,
  image,
  signature,
  table,
  Table: table,
  line,
  rectangle,
  ellipse,
  svg,
  list,
  multiVariableText,
  date,
  dateTime,
  time,
  select,
  checkbox,
  radioGroup,
  circleMark,
};

const pdf = await generate({
  template,
  inputs: Array.isArray(job.inputs) ? job.inputs : [{}],
  plugins,
});

fs.writeFileSync(job.output, pdf);
