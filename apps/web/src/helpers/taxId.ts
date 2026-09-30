/**
 * Validacion del NIF (DNI), NIE y CIF espanoles, con su caracter de control.
 *
 * Duplica a proposito la del backend (`TaxId`): avisa al escribir, pero el API
 * vuelve a validar y responde `INVALID_TAX_ID`.
 */

const DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE";
const CIF_LETTER_CONTROL = "PQRSNW";
const CIF_DIGIT_CONTROL = "ABEH";

export type TaxIdKind = "dni" | "nie" | "cif";

export function normalizeTaxId(raw: string): string {
  return raw.replace(/[\s.-]/g, "").toUpperCase();
}

function cifControl(digits: string): [string, string] {
  let total = 0;
  for (let index = 0; index < digits.length; index += 1) {
    const value = Number(digits[index]);
    if (index % 2 === 0) {
      const doubled = value * 2;
      total += Math.floor(doubled / 10) + (doubled % 10);
    } else {
      total += value;
    }
  }
  const control = (10 - (total % 10)) % 10;
  return [String(control), "JABCDEFGHI"[control] ?? ""];
}

export function taxIdKind(raw: string): TaxIdKind | null {
  const value = normalizeTaxId(raw);
  const dni = /^(\d{8})([A-Z])$/.exec(value);
  if (dni) {
    return DNI_LETTERS[Number(dni[1]) % 23] === dni[2] ? "dni" : null;
  }
  const nie = /^([XYZ])(\d{7})([A-Z])$/.exec(value);
  if (nie) {
    const number = Number(`${"XYZ".indexOf(nie[1] ?? "")}${nie[2]}`);
    return DNI_LETTERS[number % 23] === nie[3] ? "nie" : null;
  }
  const cif = /^([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-J])$/.exec(value);
  if (cif) {
    const [organization = "", digits = "", control = ""] = cif.slice(1);
    const [digit, letter] = cifControl(digits);
    if (CIF_LETTER_CONTROL.includes(organization)) return control === letter ? "cif" : null;
    if (CIF_DIGIT_CONTROL.includes(organization)) return control === digit ? "cif" : null;
    return control === digit || control === letter ? "cif" : null;
  }
  return null;
}
