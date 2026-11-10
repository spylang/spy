/*
 * <ai>SPy-friendly glue around the CUI immediate-mode UI library.</ai>
 *
 * <ai>The C backend calls the `spy_cui$*` functions below. Each one takes
 * spy_StrObject pointers and scalars, exactly like the qrcodegen example.
 * The `pycui$*` functions are the same API but take plain `const char *`
 * strings: the interpreted backend reaches them through ctypes, because a
 * spy_StrObject lives in libspy's WASM linear memory and cannot be handed to
 * a native shared library.</ai>
 */
#ifndef SPYVM_CUI_H
#define SPYVM_CUI_H

#include <spy.h>
#include <spy/str.h>

/* ===== C backend API ===== */

bool spy_cui$app_create(spy_StrObject *title, int32_t width, int32_t height);
bool spy_cui$app_frame(void);
void spy_cui$app_destroy(void);

void spy_cui$page_begin(void);
void spy_cui$page_end(void);
void spy_cui$column_begin(double pad, double gap);
void spy_cui$column_fill_begin(double pad, double gap);
void spy_cui$column_max_begin(double pad, double gap, double max_width);
void spy_cui$column_end(void);
void spy_cui$row_begin(double gap);
void spy_cui$row_fill_begin(double gap);
void spy_cui$row_end(void);
void spy_cui$scroll_begin(spy_StrObject *id);
void spy_cui$scroll_end(void);
void spy_cui$spacer(void);
void spy_cui$separator(void);

void spy_cui$heading(spy_StrObject *text, int32_t level);
void spy_cui$text(spy_StrObject *text);
void spy_cui$secondary(spy_StrObject *text);
void spy_cui$label(spy_StrObject *text);
void spy_cui$badge(spy_StrObject *text, int32_t tone);
void spy_cui$toast(spy_StrObject *text);
void spy_cui$progress(double value);

bool spy_cui$button(spy_StrObject *label, bool primary);
bool spy_cui$icon_button(spy_StrObject *icon);
bool spy_cui$switch(spy_StrObject *label, bool value);
bool spy_cui$checkbox(spy_StrObject *label, bool value);
double spy_cui$slider(spy_StrObject *label, double value, double lo, double hi);
int32_t spy_cui$segmented(spy_StrObject *id, spy_StrObject *items, int32_t index);

spy_StrObject *spy_cui$input(spy_StrObject *id, spy_StrObject *label,
                             spy_StrObject *placeholder);
void spy_cui$input_clear(spy_StrObject *id);
bool spy_cui$input_submitted(void);
bool spy_cui$input_changed(void);

void spy_cui$push_id_int(int32_t n);
void spy_cui$pop_id(void);

bool spy_cui$dialog_begin(spy_StrObject *title, spy_StrObject *description, bool open);
void spy_cui$dialog_end(void);
void spy_cui$dialog_footer_begin(void);
void spy_cui$dialog_footer_end(void);

/* ===== ctypes API (interpreted mode) ===== */

void *pycui$app_create(const char *title, int32_t width, int32_t height);
bool pycui$app_frame(void);
void pycui$app_destroy(void);

void pycui$page_begin(void);
void pycui$page_end(void);
void pycui$column_begin(double pad, double gap);
void pycui$column_fill_begin(double pad, double gap);
void pycui$column_max_begin(double pad, double gap, double max_width);
void pycui$column_end(void);
void pycui$row_begin(double gap);
void pycui$row_fill_begin(double gap);
void pycui$row_end(void);
void pycui$scroll_begin(const char *id);
void pycui$scroll_end(void);
void pycui$spacer(void);
void pycui$separator(void);

void pycui$heading(const char *text, int32_t level);
void pycui$text(const char *text);
void pycui$secondary(const char *text);
void pycui$label(const char *text);
void pycui$badge(const char *text, int32_t tone);
void pycui$toast(const char *text);
void pycui$progress(double value);

bool pycui$button(const char *label, bool primary);
bool pycui$icon_button(const char *icon);
bool pycui$switch(const char *label, bool value);
bool pycui$checkbox(const char *label, bool value);
double pycui$slider(const char *label, double value, double lo, double hi);
int32_t pycui$segmented(const char *id, const char *items, int32_t index);

const char *pycui$input(const char *id, const char *label, const char *placeholder);
void pycui$input_clear(const char *id);
bool pycui$input_submitted(void);
bool pycui$input_changed(void);

void pycui$push_id_int(int32_t n);
void pycui$pop_id(void);

bool pycui$dialog_begin(const char *title, const char *description, bool open);
void pycui$dialog_end(void);
void pycui$dialog_footer_begin(void);
void pycui$dialog_footer_end(void);

#endif /* SPYVM_CUI_H */
