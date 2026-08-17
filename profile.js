const ageElements = document.querySelectorAll('[data-age]');
const birthDateValue = ageElements[0]?.getAttribute('datetime');

if (birthDateValue) {
  const [birthYear, birthMonth, birthDay] = birthDateValue.split('-').map(Number);
  const today = new Date();
  let age = today.getFullYear() - birthYear;
  const birthdayHasPassed =
    today.getMonth() + 1 > birthMonth ||
    (today.getMonth() + 1 === birthMonth && today.getDate() >= birthDay);

  if (!birthdayHasPassed) age -= 1;

  for (const element of ageElements) {
    element.textContent = `${age} ans`;
  }
}
