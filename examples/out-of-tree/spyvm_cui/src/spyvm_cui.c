/*
 * <ai>SPy-friendly glue around CUI. See spyvm_cui.h for the two APIs.</ai>
 */
#include "spyvm_cui.h"

#include <stdio.h>
#include <string.h>

#include "cui.h"

#define KEYMAX 128
#define INPUT_CAP 1024
#define MAX_SLOTS 256

static cui_app *g_app = NULL;
static cui_ctx *g_ui = NULL;
static int g_input_flags = 0;

typedef struct {
    char key[KEYMAX];
    bool val;
} BSlot;

typedef struct {
    char key[KEYMAX];
    int val;
} ISlot;

typedef struct {
    char key[KEYMAX];
    float val;
} FSlot;

typedef struct {
    char key[KEYMAX];
    char buf[INPUT_CAP];
} InputSlot;

static BSlot g_bools[MAX_SLOTS];
static int g_nbools;
static ISlot g_ints[MAX_SLOTS];
static int g_nints;
static FSlot g_floats[MAX_SLOTS];
static int g_nfloats;
static InputSlot g_inputs[MAX_SLOTS];
static int g_ninputs;

static void reset_state(void) {
    g_nbools = g_nints = g_nfloats = g_ninputs = 0;
    g_input_flags = 0;
}

static BSlot *bool_slot(const char *key, bool init) {
    int i;
    for (i = 0; i < g_nbools; i++) {
        if (strcmp(g_bools[i].key, key) == 0) return &g_bools[i];
    }
    BSlot *s = &g_bools[g_nbools++];
    snprintf(s->key, sizeof s->key, "%s", key);
    s->val = init;
    return s;
}

static ISlot *int_slot(const char *key, int init) {
    int i;
    for (i = 0; i < g_nints; i++) {
        if (strcmp(g_ints[i].key, key) == 0) return &g_ints[i];
    }
    ISlot *s = &g_ints[g_nints++];
    snprintf(s->key, sizeof s->key, "%s", key);
    s->val = init;
    return s;
}

static FSlot *float_slot(const char *key, float init) {
    int i;
    for (i = 0; i < g_nfloats; i++) {
        if (strcmp(g_floats[i].key, key) == 0) return &g_floats[i];
    }
    FSlot *s = &g_floats[g_nfloats++];
    snprintf(s->key, sizeof s->key, "%s", key);
    s->val = init;
    return s;
}

static InputSlot *input_slot(const char *key) {
    int i;
    for (i = 0; i < g_ninputs; i++) {
        if (strcmp(g_inputs[i].key, key) == 0) return &g_inputs[i];
    }
    InputSlot *s = &g_inputs[g_ninputs++];
    snprintf(s->key, sizeof s->key, "%s", key);
    s->buf[0] = '\0';
    return s;
}

static bool core_app_create(const char *title, int width, int height) {
    reset_state();
    cui_app_desc desc;
    memset(&desc, 0, sizeof desc);
    desc.title = title;
    desc.width = width;
    desc.height = height;
    g_app = cui_app_create(&desc);
    if (g_app == NULL) return false;
    g_ui = cui_app_ui(g_app);
    return true;
}

static bool core_app_frame(void) {
    if (g_app == NULL) return false;
    bool ok = cui_app_frame(g_app);
    if (ok) g_ui = cui_app_ui(g_app);
    return ok;
}

static void core_app_destroy(void) {
    if (g_app != NULL) {
        cui_app_destroy(g_app);
        g_app = NULL;
        g_ui = NULL;
    }
}

static void core_page_begin(void) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_COLUMN;
    b.width = CUI_FILL;
    b.height = CUI_FILL;
    b.align = CUI_ALIGN_CENTER;
    b.bg = CUI_COLOR_BACKGROUND;
    cui_box_begin(g_ui, &b);
}

static void core_page_end(void) { cui_box_end(g_ui); }

static void core_column_begin(double pad, double gap) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_COLUMN;
    b.pad = (float)pad;
    b.gap = (float)gap;
    cui_column_begin(g_ui, &b);
}

static void core_column_fill_begin(double pad, double gap) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_COLUMN;
    b.width = CUI_FILL;
    b.height = CUI_FILL;
    b.pad = (float)pad;
    b.gap = (float)gap;
    cui_column_begin(g_ui, &b);
}

static void core_column_max_begin(double pad, double gap, double max_width) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_COLUMN;
    b.width = CUI_FILL;
    b.height = CUI_FILL;
    b.max_width = (float)max_width;
    b.pad = (float)pad;
    b.gap = (float)gap;
    cui_column_begin(g_ui, &b);
}

static void core_column_end(void) { cui_box_end(g_ui); }

static void core_row_begin(double gap) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_ROW;
    b.gap = (float)gap;
    b.align = CUI_ALIGN_CENTER;
    cui_row_begin(g_ui, &b);
}

static void core_row_fill_begin(double gap) {
    cui_box b;
    memset(&b, 0, sizeof b);
    b.dir = CUI_ROW;
    b.width = CUI_FILL;
    b.gap = (float)gap;
    b.align = CUI_ALIGN_CENTER;
    cui_row_begin(g_ui, &b);
}

static void core_row_end(void) { cui_box_end(g_ui); }

static void core_scroll_begin(const char *id) {
    cui_scroll_opts o;
    memset(&o, 0, sizeof o);
    o.id = id;
    o.width = CUI_FILL;
    o.height = CUI_FILL;
    o.gap = 2;
    cui_scroll_begin(g_ui, &o);
}

static void core_scroll_end(void) { cui_scroll_end(g_ui); }

static void core_spacer(void) { cui_spacer(g_ui); }
static void core_separator(void) { cui_separator(g_ui); }

static void core_heading(const char *text, int level) {
    cui_heading(g_ui, text, level);
}

static void core_text(const char *text) { cui_text(g_ui, text); }

static void core_secondary(const char *text) { cui_secondary(g_ui, text); }

static void core_label(const char *text) { cui_label(g_ui, text); }

static void core_badge(const char *text, int tone) {
    cui_badge_opts o;
    memset(&o, 0, sizeof o);
    o.tone = (cui_tone)tone;
    cui_badge_ex(g_ui, text, &o);
}

static void core_toast(const char *text) {
    cui_toast_opts o;
    memset(&o, 0, sizeof o);
    cui_toast_ex(g_ui, text, &o);
}

static void core_progress(double value) {
    cui_progress_opts o;
    memset(&o, 0, sizeof o);
    cui_progress_ex(g_ui, (float)value, &o);
}

static bool core_button(const char *label, bool primary) {
    cui_button_opts o;
    memset(&o, 0, sizeof o);
    o.variant = primary ? CUI_BUTTON_PRIMARY : CUI_BUTTON_DEFAULT;
    return cui_button_ex(g_ui, label, &o);
}

static bool core_icon_button(const char *icon) {
    cui_button_opts o;
    memset(&o, 0, sizeof o);
    o.variant = CUI_BUTTON_GHOST;
    o.size = CUI_SIZE_SM;
    return cui_icon_button_ex(g_ui, icon, &o);
}

static bool core_switch(const char *label, bool value) {
    char key[KEYMAX];
    snprintf(key, sizeof key, "sw:%s", label);
    BSlot *s = bool_slot(key, value);
    cui_check_opts o;
    memset(&o, 0, sizeof o);
    cui_switch_ex(g_ui, label, &s->val, &o);
    return s->val;
}

static bool core_checkbox(const char *label, bool value) {
    char key[KEYMAX];
    snprintf(key, sizeof key, "cb:%s", label);
    BSlot *s = bool_slot(key, value);
    cui_check_opts o;
    memset(&o, 0, sizeof o);
    cui_checkbox_ex(g_ui, label, &s->val, &o);
    return s->val;
}

static double core_slider(const char *label, double value, double lo, double hi) {
    char key[KEYMAX];
    snprintf(key, sizeof key, "sld:%s", label);
    FSlot *s = float_slot(key, (float)value);
    cui_slider_opts o;
    memset(&o, 0, sizeof o);
    o.show_value = true;
    cui_slider_ex(g_ui, label, &s->val, (float)lo, (float)hi, &o);
    return (double)s->val;
}

/* <ai>Split a `a|b|c` string into up to 32 NUL-terminated items, in place.</ai> */
static int split_items(char *copy, const char **items, int max_items) {
    int n = 0;
    char *p = copy;
    while (*p != '\0' && n < max_items) {
        items[n++] = p;
        char *sep = strchr(p, '|');
        if (sep == NULL) break;
        *sep = '\0';
        p = sep + 1;
    }
    return n;
}

static int core_segmented(const char *id, const char *items, int index) {
    char key[KEYMAX];
    snprintf(key, sizeof key, "seg:%s", id);
    ISlot *s = int_slot(key, index);
    char copy[512];
    snprintf(copy, sizeof copy, "%s", items);
    const char *arr[32];
    int n = split_items(copy, arr, 32);
    cui_segmented_opts o;
    memset(&o, 0, sizeof o);
    cui_segmented_ex(g_ui, id, arr, n, &s->val, &o);
    return s->val;
}

static const char *core_input(const char *id, const char *label,
                              const char *placeholder) {
    InputSlot *s = input_slot(id);
    cui_input_opts o;
    memset(&o, 0, sizeof o);
    o.label = label;
    o.placeholder = placeholder;
    g_input_flags = cui_input_ex(g_ui, id, s->buf, INPUT_CAP, &o);
    return s->buf;
}

static void core_input_clear(const char *id) {
    InputSlot *s = input_slot(id);
    s->buf[0] = '\0';
}

static bool core_input_submitted(void) { return (g_input_flags & CUI_SUBMITTED) != 0; }
static bool core_input_changed(void) { return (g_input_flags & CUI_CHANGED) != 0; }

static void core_push_id_int(int n) { cui_push_id_int(g_ui, n); }
static void core_pop_id(void) { cui_pop_id(g_ui); }

static bool core_dialog_begin(const char *title, const char *desc, bool open) {
    char key[KEYMAX];
    snprintf(key, sizeof key, "dlg:%s", title);
    BSlot *s = bool_slot(key, open);
    s->val = open;
    cui_dialog_opts o;
    memset(&o, 0, sizeof o);
    o.description = desc;
    cui_dialog_begin(g_ui, title, &s->val, &o);
    return s->val;
}

static void core_dialog_end(void) { cui_dialog_end(g_ui); }
static void core_dialog_footer_begin(void) { cui_dialog_footer_begin(g_ui); }
static void core_dialog_footer_end(void) { cui_dialog_footer_end(g_ui); }

/* ===== C backend wrappers: spy_StrObject -> const char * ===== */

#ifndef SPYVM_CUI_CTYPES_ONLY

#define SARG(name, obj)                                                        \
    char name##_buf[INPUT_CAP];                                                \
    size_t name##_n = (obj)->length;                                           \
    if (name##_n >= sizeof name##_buf) name##_n = sizeof name##_buf - 1;       \
    memcpy(name##_buf, spy_StrObject_CHARS(obj), name##_n);                    \
    name##_buf[name##_n] = '\0';                                               \
    const char *name = name##_buf

#define SARG2(a, b, oa, ob) \
    SARG(a, oa);            \
    SARG(b, ob)

static spy_StrObject *wrap_cstr(const char *s) {
    size_t n = strlen(s);
    spy_StrObject *res = spy_str_alloc(n);
    memcpy((char *)spy_StrObject_CHARS(res), s, n);
    spy_str_seal(res);
    return res;
}

bool spy_cui$app_create(spy_StrObject *title, int32_t width, int32_t height) {
    SARG(t, title);
    return core_app_create(t, width, height);
}

bool spy_cui$app_frame(void) { return core_app_frame(); }
void spy_cui$app_destroy(void) { core_app_destroy(); }

void spy_cui$page_begin(void) { core_page_begin(); }
void spy_cui$page_end(void) { core_page_end(); }
void spy_cui$column_begin(double pad, double gap) { core_column_begin(pad, gap); }
void spy_cui$column_fill_begin(double pad, double gap) { core_column_fill_begin(pad, gap); }
void spy_cui$column_max_begin(double pad, double gap, double max_width) {
    core_column_max_begin(pad, gap, max_width);
}
void spy_cui$column_end(void) { core_column_end(); }
void spy_cui$row_begin(double gap) { core_row_begin(gap); }
void spy_cui$row_fill_begin(double gap) { core_row_fill_begin(gap); }
void spy_cui$row_end(void) { core_row_end(); }
void spy_cui$spacer(void) { core_spacer(); }
void spy_cui$separator(void) { core_separator(); }

void spy_cui$scroll_begin(spy_StrObject *id) {
    SARG(i, id);
    core_scroll_begin(i);
}
void spy_cui$scroll_end(void) { core_scroll_end(); }

void spy_cui$heading(spy_StrObject *text, int32_t level) {
    SARG(t, text);
    core_heading(t, level);
}
void spy_cui$text(spy_StrObject *text) {
    SARG(t, text);
    core_text(t);
}
void spy_cui$secondary(spy_StrObject *text) {
    SARG(t, text);
    core_secondary(t);
}
void spy_cui$label(spy_StrObject *text) {
    SARG(t, text);
    core_label(t);
}
void spy_cui$badge(spy_StrObject *text, int32_t tone) {
    SARG(t, text);
    core_badge(t, tone);
}
void spy_cui$toast(spy_StrObject *text) {
    SARG(t, text);
    core_toast(t);
}
void spy_cui$progress(double value) { core_progress(value); }

bool spy_cui$button(spy_StrObject *label, bool primary) {
    SARG(l, label);
    return core_button(l, primary);
}
bool spy_cui$icon_button(spy_StrObject *icon) {
    SARG(i, icon);
    return core_icon_button(i);
}
bool spy_cui$switch(spy_StrObject *label, bool value) {
    SARG(l, label);
    return core_switch(l, value);
}
bool spy_cui$checkbox(spy_StrObject *label, bool value) {
    SARG(l, label);
    return core_checkbox(l, value);
}
double spy_cui$slider(spy_StrObject *label, double value, double lo, double hi) {
    SARG(l, label);
    return core_slider(l, value, lo, hi);
}
int32_t spy_cui$segmented(spy_StrObject *id, spy_StrObject *items, int32_t index) {
    SARG2(i, it, id, items);
    return core_segmented(i, it, index);
}
spy_StrObject *spy_cui$input(spy_StrObject *id, spy_StrObject *label,
                             spy_StrObject *placeholder) {
    SARG(i, id);
    SARG(l, label);
    SARG(p, placeholder);
    return wrap_cstr(core_input(i, l, p));
}
void spy_cui$input_clear(spy_StrObject *id) {
    SARG(i, id);
    core_input_clear(i);
}
bool spy_cui$input_submitted(void) { return core_input_submitted(); }
bool spy_cui$input_changed(void) { return core_input_changed(); }

void spy_cui$push_id_int(int32_t n) { core_push_id_int(n); }
void spy_cui$pop_id(void) { core_pop_id(); }

bool spy_cui$dialog_begin(spy_StrObject *title, spy_StrObject *description, bool open) {
    SARG2(t, d, title, description);
    return core_dialog_begin(t, d, open);
}
void spy_cui$dialog_end(void) { core_dialog_end(); }
void spy_cui$dialog_footer_begin(void) { core_dialog_footer_begin(); }
void spy_cui$dialog_footer_end(void) { core_dialog_footer_end(); }

#endif /* !SPYVM_CUI_CTYPES_ONLY */

/* ===== ctypes wrappers: plain C strings ===== */

void *pycui$app_create(const char *title, int32_t width, int32_t height) {
    return core_app_create(title, width, height) ? (void *)g_app : NULL;
}
bool pycui$app_frame(void) { return core_app_frame(); }
void pycui$app_destroy(void) { core_app_destroy(); }

void pycui$page_begin(void) { core_page_begin(); }
void pycui$page_end(void) { core_page_end(); }
void pycui$column_begin(double pad, double gap) { core_column_begin(pad, gap); }
void pycui$column_fill_begin(double pad, double gap) { core_column_fill_begin(pad, gap); }
void pycui$column_max_begin(double pad, double gap, double max_width) {
    core_column_max_begin(pad, gap, max_width);
}
void pycui$column_end(void) { core_column_end(); }
void pycui$row_begin(double gap) { core_row_begin(gap); }
void pycui$row_fill_begin(double gap) { core_row_fill_begin(gap); }
void pycui$row_end(void) { core_row_end(); }
void pycui$scroll_begin(const char *id) { core_scroll_begin(id); }
void pycui$scroll_end(void) { core_scroll_end(); }
void pycui$spacer(void) { core_spacer(); }
void pycui$separator(void) { core_separator(); }

void pycui$heading(const char *text, int32_t level) { core_heading(text, level); }
void pycui$text(const char *text) { core_text(text); }
void pycui$secondary(const char *text) { core_secondary(text); }
void pycui$label(const char *text) { core_label(text); }
void pycui$badge(const char *text, int32_t tone) { core_badge(text, tone); }
void pycui$toast(const char *text) { core_toast(text); }
void pycui$progress(double value) { core_progress(value); }

bool pycui$button(const char *label, bool primary) { return core_button(label, primary); }
bool pycui$icon_button(const char *icon) { return core_icon_button(icon); }
bool pycui$switch(const char *label, bool value) { return core_switch(label, value); }
bool pycui$checkbox(const char *label, bool value) { return core_checkbox(label, value); }
double pycui$slider(const char *label, double value, double lo, double hi) {
    return core_slider(label, value, lo, hi);
}
int32_t pycui$segmented(const char *id, const char *items, int32_t index) {
    return core_segmented(id, items, index);
}
const char *pycui$input(const char *id, const char *label, const char *placeholder) {
    return core_input(id, label, placeholder);
}
void pycui$input_clear(const char *id) { core_input_clear(id); }
bool pycui$input_submitted(void) { return core_input_submitted(); }
bool pycui$input_changed(void) { return core_input_changed(); }

void pycui$push_id_int(int32_t n) { core_push_id_int(n); }
void pycui$pop_id(void) { core_pop_id(); }

bool pycui$dialog_begin(const char *title, const char *description, bool open) {
    return core_dialog_begin(title, description, open);
}
void pycui$dialog_end(void) { core_dialog_end(); }
void pycui$dialog_footer_begin(void) { core_dialog_footer_begin(); }
void pycui$dialog_footer_end(void) { core_dialog_footer_end(); }
