import { prisma } from '../src/lib/prisma';
import { ALL_UNITS } from '../src/lib/units/constants';

async function seedUnits() {
  console.log('Seeding units...');
  for (const [key, unit] of Object.entries(ALL_UNITS)) {
    await prisma.unit.upsert({
      where: { name: key },
      update: {},
      create: {
        name: key,
        abbreviation: unit.abbreviations[0],
        type: unit.type,
        toBaseFactor: unit.toBase,
        baseUnit: unit.baseUnit,
      },
    });
  }
  console.log('Done!');
}

seedUnits()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
