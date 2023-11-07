export const isPC =
  !/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );

export const hideDom = (el) => {
  el.classList.add('hidden');
};

export const showDom = (el) => {
  el.classList.remove('hidden');
};

export const disableBtn = (el) => {
  el.classList.add('disabled');
};

export const activeBtn = (el) => {
  el.classList.remove('disabled');
};
