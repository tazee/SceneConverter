#python

'''

    Utility command plugin to export scene files to destination
    folder.

'''

import lx
import lxifc
import lxu.command
import lxu.select
import modo
from lxifc import UIValueHints

import os
import logging
import datetime
import pathlib
import shutil

from collections import namedtuple

DynamicAttribute = namedtuple('DynamicAttribute', ['name', 'index'])

ATTR_SFOLDER = DynamicAttribute('srcFolder',  0)
ATTR_SFORMAT = DynamicAttribute('srcFormat',  1)
ATTR_DFOLDER = DynamicAttribute('dstFolder',  2)
ATTR_DFORMAT = DynamicAttribute('dstFormat',  3)
ATTR_COPYIMG = DynamicAttribute('copyImages', 4)
ATTR_MAKELOG = DynamicAttribute('makeLog',    5)
ATTR_LOGFILE = DynamicAttribute('logFile',    6)
ATTR_COMMENT = DynamicAttribute('comment',    7)

class FormatPopup(lxifc.UIValueHints):
    def __init__(self,formats):
        self.formats = formats

    def uiv_Flags(self):
        return lx.symbol.fVALHINT_POPUPS

    def uiv_PopCount(self):
        return len(self.formats)

    def uiv_PopUserName(self,index):
        name, format, ext =  self.formats[index]
        return name

    def uiv_PopInternalName(self,index):
        name, format, ext =  self.formats[index]
        return name

class SceneConverter_Cmd(lxu.command.BasicCommand):
    def __init__(self):
        lxu.command.BasicCommand.__init__(self)
    
        self.dyna_Add(ATTR_SFOLDER.name, lx.symbol.sTYPE_FILEPATH)
        self.dyna_Add(ATTR_SFORMAT.name, lx.symbol.sTYPE_INTEGER)
        self.dyna_Add(ATTR_DFOLDER.name, lx.symbol.sTYPE_FILEPATH)
        self.dyna_Add(ATTR_DFORMAT.name, lx.symbol.sTYPE_INTEGER)
        self.dyna_Add(ATTR_COPYIMG.name, lx.symbol.sTYPE_BOOLEAN)
        self.dyna_Add(ATTR_MAKELOG.name, lx.symbol.sTYPE_BOOLEAN)
        self.dyna_Add(ATTR_LOGFILE.name, lx.symbol.sTYPE_FILEPATH)
        self.dyna_Add(ATTR_COMMENT.name, lx.symbol.sTYPE_STRING)
    
        if modo.Scene().filename != None:
            self.srcFolder = os.path.dirname(modo.Scene().filename)
        else:
            srvFile = lx.service.File()
            self.srcFolder = srvFile.FileSystemPath(lx.symbol.sSYSTEM_PATH_DOCUMENTS)
        self.srcFormat = 0
        self.dstFolder = self.srcFolder
        self.dstFormat = 1
        self.copyImages = False
        self.makeLog = True
        self.logFile = 'log.txt'
        self.comment = ''

        self.formats= [('Modo Scene (*.lxo)', '$LXOB', '.lxo'), \
                        ('Autodesk FBX 2000 (*.fbx)', 'fbx', '.fbx'), \
                        ('Alembic Format (*.abc)', 'Alembic', '.abc'), \
                        ('COLLADA 1.4.1 (*.dae)', 'COLLADA_141', '.dae'), \
                        ('Pixar USD (*.usd)', 'USD_FORMAT_USD', '.usd'), \
                        ('LightWave Object (*.lwo)', '$NLWO2', '.lwo')]


    def cmd_DialogInit (self):
        if not self.dyna_IsSet (ATTR_SFOLDER.index):
            self.attr_SetString (ATTR_SFOLDER.index, self.srcFolder)
        if not self.dyna_IsSet (ATTR_SFORMAT.index):
            self.attr_SetInt (ATTR_SFORMAT.index, self.srcFormat)
        if not self.dyna_IsSet (ATTR_DFOLDER.index):
            self.attr_SetString (ATTR_DFOLDER.index, self.dstFolder)
        if not self.dyna_IsSet (ATTR_DFORMAT.index):
            self.attr_SetInt (ATTR_DFORMAT.index, self.dstFormat)
        if not self.dyna_IsSet (ATTR_COPYIMG.index):
            self.attr_SetInt (ATTR_COPYIMG.index, self.copyImages)
        if not self.dyna_IsSet (ATTR_MAKELOG.index):
            self.attr_SetInt (ATTR_MAKELOG.index, self.makeLog)
        if not self.dyna_IsSet (ATTR_LOGFILE.index):
            self.attr_SetString (ATTR_LOGFILE.index, self.logFile)
        if not self.dyna_IsSet (ATTR_COMMENT.index):
            self.attr_SetString (ATTR_COMMENT.index, self.comment)

    def cmd_Flags(self):
        return lx.symbol.fCMD_MODEL | lx.symbol.fCMD_UNDO

    def arg_UIValueHints(self, index):
        if index == ATTR_SFORMAT.index or index == ATTR_DFORMAT.index:
            return FormatPopup(self.formats)

    def cmd_ArgEnable(self, index):
        if index == ATTR_LOGFILE.index or index == ATTR_COMMENT.index:
            makeLog = self.attr_GetInt(ATTR_MAKELOG.index)
            if makeLog == False:
                lx.throw (lx.symbol.e_CMD_DISABLED)
                return False
        return True

    def CopyImages(self, dstPath):
        sel_svc = lxu.select.SceneSelection()
        scn_svc = lx.service.Scene ()
        scene = sel_svc.current()
        type  = scn_svc.ItemTypeLookup (lx.symbol.sITYPE_VIDEOSTILL)
        for idx in range (scene.ItemCount (type)):
            imgClip = modo.item.Item (scene.ItemByIndex (type, idx))
            imgPath = imgClip.channel (lx.symbol.sICHAN_VIDEOSTILL_FILENAME).get ()
            if os.path.exists(imgPath) == False:
                logging.error('\tFile Not Found: \"{}\"'.format(imgPath))
            else:
                try:
                    shutil.copy(imgPath, dstPath)
                    logging.info('\tClip: \"{}\" from \"{}\"'.format(os.path.basename(imgPath), imgPath))
                except:
                    logging.error('\tCopyError: \"{}\"'.format(imgPath))

    def ConvertScene(self, srcFilePath, newFilePath, dstFormat, dstDirname):
        '''
            Open the source scene file
        '''
        ok = True
        comstr = '!scene.open \"' + srcFilePath + '\" normal'
        try:
            lx.eval( comstr )
        except:
            logging.error('OpenError: {}'.format(comstr))
            ok = False

        '''
            Save it to the destination folder
        '''
        if ok == True:
            comstr = '!scene.saveAs \"' + newFilePath + '\" ' + dstFormat + ' false'
            try:
                lx.eval ( comstr )
                reldst = os.path.relpath(newFilePath,self.dstFolder)
                relsrc = os.path.relpath(srcFilePath,self.srcFolder)
                logging.info('Converted: \"{}\" from \"{}\"'.format(reldst,relsrc))
            except:
                logging.error('SaveError: {}'.format(comstr))

        if ok == True and self.copyImages:
            self.CopyImages(dstDirname)

        '''
            Close the scene
        '''
        if ok == True:
            comstr = '!scene.close'
            lx.eval ( comstr )

        return ok

    def basic_Execute(self, msg, flags):
        self.srcFolder = self.attr_GetString(ATTR_SFOLDER.index)
        self.srcFormat = self.attr_GetInt(ATTR_SFORMAT.index)
        self.dstFolder = self.attr_GetString(ATTR_DFOLDER.index)
        self.dstFormat = self.attr_GetInt(ATTR_DFORMAT.index)
        self.copyImages = self.attr_GetInt(ATTR_COPYIMG.index)
        self.makeLog = self.attr_GetInt(ATTR_MAKELOG.index)
        self.logFile = self.attr_GetString(ATTR_LOGFILE.index)
        self.comment = self.attr_GetString(ATTR_COMMENT.index)

        if os.path.exists(self.srcFolder) == False:
            lx.out('SceneConvert: source folder not found {}'.format(self.srcFolder))
            return

        '''
            Set logging
        '''
        if self.makeLog == True and self.logFile != '':
            if os.path.isabs(self.logFile):
                logFilePath = self.logFile
            else:
                logFilePath = os.path.join(self.dstFolder, self.logFile)
            pathlib.Path(self.dstFolder).mkdir(parents=True, exist_ok=True)
            logging.basicConfig(level=logging.INFO, filename = logFilePath, format='%(message)s')

        dt_now = datetime.datetime.now()
        logging.info('# DateTime: {}'.format(dt_now))
        logging.info('# Source: {}'.format(self.srcFolder))
        logging.info('# Destination: {}\n'.format(self.dstFolder))
        if self.comment != '':
            logging.info('# Comment: {}\n'.format(self.comment))

        num_ok = 0
        num_fail = 0

        srcName, srcFormat, srcExtention = self.formats[self.srcFormat]
        dstName, dstFormat, dstExtention = self.formats[self.dstFormat]
        '''
            Convert a single scene file if scene file name is set to srcFolder
        '''
        if os.path.isfile(self.srcFolder):
            if self.srcFolder.endswith(srcExtention):
                srcFilename = os.path.basename(self.srcFolder)
                dstFilename = srcFilename.removesuffix(srcExtention) + dstExtention
                newFilePath = os.path.join(self.dstFolder, dstFilename)

                ok = self.ConvertScene(self.srcFolder, newFilePath, dstFormat, self.dstFolder)
                if ok == True:
                    num_ok += 1
                else:
                    num_fail += 1

        elif os.path.isdir(self.srcFolder):
            for curdir, dirs, files in os.walk(self.srcFolder):
                for file in files:
                    if file.endswith(srcExtention):
                        srcFilePath = os.path.join(curdir, file)
                        dstFilename = file.removesuffix(srcExtention) + dstExtention
                        if curdir == self.srcFolder:
                            dstDirname = self.dstFolder
                        else:
                            relPath = os.path.relpath(self.srcFolder, curdir)
                            dstDirname = os.path.join(self.dstFolder, relPath)
                        '''
                            Make the destination directories
                        '''
                        pathlib.Path(dstDirname).mkdir(parents=True, exist_ok=True)
                        newFilePath = os.path.join(dstDirname, dstFilename)

                        ok = self.ConvertScene(srcFilePath, newFilePath, dstFormat, dstDirname)
                        if ok == True:
                            num_ok += 1
                        else:
                            num_fail += 1
        
        if num_ok > 0 and num_fail == 0:
            lx.out('SceneConverter: {} scenes were converted'.format(num_ok))
        elif num_ok == 0 and num_fail > 0:
            lx.out('SceneConverter: {} scenes were failed'.format(num_fail))
        else:
            lx.out('SceneConverter: {} scenes were converted, {} failed'.format(num_ok,num_fail))

'''
    "Blessing" the class promotes it to a fist class server. This basically
    means that modo will now recognize this plugin script as a command plugin.
'''
lx.bless(SceneConverter_Cmd, "scene.converter")
