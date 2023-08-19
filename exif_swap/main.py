import os
import sys
import argparse
import re
import logging
import piexif

EMPTY_EXIF = {'0th': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}, '1st': {},
              'thumbnail': None}


class MetadataError(Exception):
    """
    Class used to signalize that metadata is empty in the input file.
    """
    def __init__(self, msg='Bad metadata in file.', *args, **kwargs):
        super().__init__(msg)


def filename_to_exif(filename: str) -> dict:
    """
    Converts the filename into exif bytecode that is ready to be inserted.
    Checks whether the filename is empty or valid.
    Supports additional keyword arguments for future support.

    """
    try:
        exif_dict = piexif.load(filename)
    except FileNotFoundError as e:
        print(f"{e}: file {filename} not found.")

    file_pttrn = re.compile(r'(\w)*[_-]?'
                            r'(?P<YYYY>[0-9][0-9][0-9][0-9])'
                            r'(?P<MM>[01][0-9])'
                            r'(?P<DD>[0-3][0-9])'r'[_-]?'
                            r'(?P<hh>[012][0-9])'
                            r'(?P<mm>[0-5][0-9])'
                            r'(?P<ss>[0-5][0-9])'r'[_-]?'
                            r'(\w)*.jpg')
    if (m := file_pttrn.search(filename)) is not None:
        md = m.groupdict()
    else:
        raise NameError(
                    "File does not have the creation date in its filename."
                    )
    # possible with a regex but there is no standard library function
    # for putting named groups into a string I don't think
    bstr = bytes(
        f"{md['YYYY']}:{md['MM']}:{md['DD']} {md['hh']}:{md['mm']}:{md['ss']}",
        encoding=r'utf-8')
    exif_dict["0th"][306] = bstr
    exif_dict["Exif"][36867], exif_dict["Exif"][36868] = bstr, bstr
    logging.debug("Resulting Exif, in a Dict: %s", exif_dict)
    return exif_dict


def exif_to_filename(exif_dict: dict) -> str:
    """
    Exports the date metadata of the file - if not empty - to
    the filename.

    """
    try:
        date_bytes = exif_dict["0th"][306]
    except KeyError:
        try:
            date_bytes = exif_dict["Exif"][36867]
        except KeyError:
            try:
                date_bytes = exif_dict["Exif"][36868]
            except KeyError as exc:
                raise MetadataError(
                        "No creation time found in exif_dict") from exc
    # ugly way to check for empty metadata in file, since
    # piexif is ugly itself and doesn't erase all of the
    # R/W metadata,so the program manipulates the raw dict
    # itself
    return date_bytes.replace(b':', b'').replace(b' ', b'_').decode("utf-8")


def parse_opts(args: list) -> (str, list):
    """
    Parses options and arguments.
    """
    parser = argparse.ArgumentParser()
    exif_options = parser.add_mutually_exclusive_group()
    exif_options.add_argument("-e", "--export", action="store_true", help="\
            Export EXIF metadata and append it to filename", dest='exprt')
    exif_options.add_argument("-i", "--import", action="store_true", help="\
            Import creation time EXIF metadata from the\
            filename,and append it to file.", dest='imprt')
    exif_options.add_argument("-d", "--dump", action="store_true", help="\
            Dump and clear creation time metadata from EXIF.", dest='dmp')
    parser.add_argument("-v", "--verbose", action="store_true", help="\
            Shows debug information", dest="verbose")
    parser.add_argument("filename", type=str, help="The Filename (the Path)\
             of the JPEG image.", nargs='+')
    args = parser.parse_args(args)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    # (args)
    if args.exprt:
        return "--export", args.filename
    if args.imprt:
        return "--import", args.filename
    if args.dmp:
        return "--dump", args.filename
    return None


def main(args=None):
    """
    args = arguments list

    """

    if args is None:
        args = sys.argv[1:]
    mode, filenames = parse_opts(args)
    logging.info("Selected mode: %s, Filenames: %s", mode, filenames)

    if "--export" == mode:
        for filename in filenames:
            try:
                if (exif_dict := piexif.load(filename)) == EMPTY_EXIF:
                    raise MetadataError(msg=f"File {filename} has missing\
 EXIF metadata, unable to append to filename.")
                # re_list = re.split(r"([.]\w+)\b", filename, maxsplit=1)
                # used to do that with regex but os path is better
                path, name = os.path.split(os.path.abspath(filename))
                logging.debug("Working path-like object: %s", filename)
                logging.debug("Retrieved path and file: %s %s", path, name)
                logging.debug("Date Prefix: %s", exif_to_filename(exif_dict))
                new_filename = exif_to_filename(exif_dict) + "_" + name
                logging.debug("New Filename: %s", new_filename)
                new_path = os.path.join(path, new_filename)
                logging.debug("Using Path: %s", new_path)
                os.rename(filename, new_path)
            except FileNotFoundError as e:
                print(f"{e}: file {filename} not found.")
                break

    elif "--import" == mode:
        for filename in filenames:
            piexif.insert(piexif.dump(filename_to_exif(filename)), filename)
            # Insert only accepts bytes,so we have to convert
            # the dict to bytes first
    elif "--dump" == mode:
        for filename in filenames:
            try:
                exif_dict = piexif.load(filename)
                del exif_dict["0th"][306]
                del exif_dict["Exif"][36867], exif_dict["Exif"][36868]
            except FileNotFoundError as e:
                print(f"{e}: file {filename} not found.")
                break
            except KeyError as e:
                print(f"Warning: Exif tag {e} is empty, skipping...")
            piexif.insert(piexif.dump(exif_dict), filename)

# the program receives opts and args through argv,which are UNIX filenames.
# then, the program shall depending on the commandline option:
# Read EXIF and append the date to filename
# Read the filename, and append its date to EXIF.
# Reading said EXIF shall be done with regex in both steps or the second one.
