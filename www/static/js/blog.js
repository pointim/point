$(document).ready(function() {
    // Common send form function
    function send_form_by_ctrl_enter(evt) {
        if ((evt.keyCode === 10 || evt.keyCode === 13) && (evt.ctrlKey || evt.metaKey)) {
            evt.stopPropagation();
            evt.preventDefault();
            $(this).closest("form").submit();
        }
    }

    var $post_text = $("#new-post-form #text-input");
    var $post_tags = $("#new-post-form #tags-input");
    var $post_private = $("#new-post-form #new-post-private-cb");

    // Listeners
    // New post form
    $post_text.on("keydown", send_form_by_ctrl_enter);
    // Comments reply form
    $("#content").on("keydown", ".reply-form textarea", send_form_by_ctrl_enter);

    // Delete post or comment
    $(document).on("click", ".post .edit-buttons .del", function (evt) {
        if (!confirm($(evt.target).data("confirm"))) {
            evt.preventDefault();
        }
    });

    // Scroll line numbers
    $('.codehilitetable').each(function() {
      var lines = $('.linenos pre', this);
      if (lines.length === 0) {
        //return;
      }
      $('.codehilite pre', this).on('scroll', function(evt) {
        lines.scrollTop($(this).scrollTop());
      });
    });

    // Store unsubmitted post text
    var post_input_timeout;
    var post_key = 'new_post_text';

    function post_input_store() {
        localStorage.setItem(post_key, JSON.stringify({
            text: $post_text.val(),
            tags: $post_tags.val(),
            private: $post_private.prop('checked')
        }));
    }

    function post_input_handler (evt) {
        clearTimeout(post_input_timeout);
        post_input_timeout = setTimeout(post_input_store, 400);
    }

    $post_text.on('input', post_input_handler);
    $post_tags.on('input', post_input_handler);
    $post_private.on('click', post_input_handler);

    if (window.clear_post_input) {
        // Clear stored post data
        localStorage.removeItem(post_key);
    } else {
        // Restore post form
        try {
            var post_data = JSON.parse(localStorage.getItem(post_key));
            if (post_data instanceof Object) {
                $post_text.val(post_data.text);
                $post_tags.val(post_data.tags);
                $post_private.prop('checked', post_data.private);
            }
        } catch (e) {}
    }

    // jQuery Magnific Popup for images in posts
    $('.postimg:not(.youtube)').magnificPopup({
        type: 'image'
    });
});

