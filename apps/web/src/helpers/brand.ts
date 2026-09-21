/** Partido del logotipo de texto. */

/**
 * Separa el nombre de marca en la parte neutra y la que va en amarillo.
 *
 * El acento cae siempre en la ultima palabra ("Voy a **Reformar**"), asi que
 * traducir o cambiar el nombre no obliga a tocar la cabecera ni el pie.
 */
export function splitBrand(appName: string): { lead: string; tail: string } {
  const words = appName.trim().split(/\s+/);
  const tail = words.pop() ?? appName;
  return { lead: words.join(" "), tail };
}
